"""Crash-safe synchronization execution, journaling, verification, and recovery."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from .errors import ConflictError, InjectedCrash, LockError, PathSafetyError, RecoveryRequired, StalePlanError, StateError
from .faults import FaultInjector
from .model import Entry, JOURNAL_VERSION, Operation, Plan, Snapshot
from .planner import build_plan
from .scanner import DEFAULT_IGNORES, scan_tree
from .state import StateStore
from .util import confined_path, file_sha256, fsync_dir, read_checked_json, sha256_json, validate_relpath


class SyncPair:
    def __init__(self, left: Path | str, right: Path | str):
        self.left = Path(left).resolve(strict=True)
        self.right = Path(right).resolve(strict=True)
        if self.left == self.right:
            raise PathSafetyError("LEFT and RIGHT must be distinct roots")
        if not self.left.is_dir() or not self.right.is_dir() or self.left.is_symlink() or self.right.is_symlink():
            raise PathSafetyError("LEFT and RIGHT must be existing real directories")
        self.state = StateStore(self.left, self.right)

    @classmethod
    def open(cls, left: Path | str, right: Path | str) -> "SyncPair":
        return cls(left, right)

    def init(self, ignore_patterns: list[str] | None = None) -> dict[str, Any]:
        patterns = list(DEFAULT_IGNORES if ignore_patterns is None else tuple(DEFAULT_IGNORES) + tuple(ignore_patterns))
        self.state.ensure_layout(patterns)
        pair = self.state.validate_pair()
        return {"pair_id": pair["pair_id"], "state_version": pair["version"], "state_dir": str(self.state.root)}

    def _patterns(self) -> tuple[str, ...]:
        return self.state.ignore_patterns(DEFAULT_IGNORES)

    def _snapshots(self) -> tuple[Snapshot, Snapshot]:
        patterns = self._patterns()
        return scan_tree(self.left, patterns), scan_tree(self.right, patterns)

    def plan(self) -> Plan:
        baseline = self.state.load_baseline() if self.state.baseline_path.exists() else None
        baseline_id, baseline_snapshot = baseline if baseline else (None, None)
        left, right = self._snapshots()
        return build_plan(left, right, baseline_snapshot, baseline_id)

    def status(self) -> dict[str, Any]:
        baseline = self.state.load_baseline() if self.state.baseline_path.exists() else None
        incompletes = self.state.incomplete_journals() if self.state.journal_dir.exists() else []
        plan = self.plan()
        left, right = self._snapshots()
        volume = sum(e.size for e in left.entries.values() if e.kind == "file") + sum(e.size for e in right.entries.values() if e.kind == "file")
        baseline_meta = read_checked_json(self.state.baseline_path) if baseline else None
        return {
            "pair_id": self.state.pair_id,
            "baseline_id": baseline[0] if baseline else None,
            "last_successful_sync_ns": baseline_meta.get("committed_ns") if baseline_meta else None,
            "pending_operations": len(plan.operations),
            "detected_conflicts": len(plan.conflicts),
            "incomplete_prior_run": bool(incompletes),
            "incomplete_run_ids": [p[1]["run_id"] for p in incompletes],
            "tracked_path_count": len((baseline[1].entries if baseline else {})),
            "current_path_count": {"left": len(left.entries), "right": len(right.entries)},
            "data_volume_bytes": volume,
            "plan_id": plan.id,
        }

    def verify(self) -> dict[str, Any]:
        issues: list[str] = []
        baseline = None
        try:
            baseline = self.state.load_baseline()
        except (StateError, FileNotFoundError) as exc:
            issues.append(f"baseline: {exc}")
        try:
            incompletes = self.state.incomplete_journals()
            if incompletes:
                issues.append("incomplete journal: " + ",".join(p[1]["run_id"] for p in incompletes))
        except StateError as exc:
            issues.append(f"journal: {exc}")
        try:
            left, right = self._snapshots()
            if not _snapshots_equivalent(left, right):
                issues.append("LEFT and RIGHT are not logically equivalent")
        except (PathSafetyError, OSError) as exc:
            left = right = Snapshot({})
            issues.append(f"scan: {exc}")
        artifacts = _unexpected_artifacts(self.left) + _unexpected_artifacts(self.right)
        if artifacts:
            issues.append("unexpected temporary/backup artifacts: " + ", ".join(sorted(artifacts)[:20]))
        conflicts = []
        if self.state.conflict_dir.exists():
            conflicts = sorted(p.name for p in self.state.conflict_dir.glob("*.json"))
        return {
            "ok": not issues,
            "issues": issues,
            "baseline_id": baseline[0] if baseline else None,
            "logical_equivalence": not any("not logically equivalent" in x for x in issues),
            "conflict_reports": conflicts,
            "state_version": 1,
            "journal_version": 1,
        }

    def sync(self, *, fault: FaultInjector | None = None) -> dict[str, Any]:
        self.init()
        incompletes = self.state.incomplete_journals()
        if incompletes:
            raise RecoveryRequired(f"incomplete run {incompletes[0][1]['run_id']}; run ferrosync recover")
        plan = self.plan()
        if plan.has_conflicts:
            path = self.state.record_conflicts(plan.id, [c.to_dict() for c in plan.conflicts])
            raise ConflictError(f"plan {plan.id} has {len(plan.conflicts)} conflict(s); report={path}")
        return self.apply(plan, fault=fault)

    def apply(self, plan: Plan, *, fault: FaultInjector | None = None) -> dict[str, Any]:
        """Apply an already-inspected Plan after revalidating baseline and path preconditions."""
        self.init()
        incompletes = self.state.incomplete_journals()
        if incompletes:
            raise RecoveryRequired(f"incomplete run {incompletes[0][1]['run_id']}; run ferrosync recover")
        if plan.has_conflicts:
            raise ConflictError(f"plan {plan.id} has {len(plan.conflicts)} conflict(s)")
        if self.state.baseline_path.exists() and not plan.operations:
            current = self.state.load_baseline()
            if current and current[0] == plan.baseline_id:
                return {"status": "NOOP", "plan_id": plan.id, "operations": 0, "baseline_id": plan.baseline_id}
        return self._apply_plan(plan, fault=fault or FaultInjector())

    def _apply_plan(self, plan: Plan, *, fault: FaultInjector) -> dict[str, Any]:
        current_baseline = self.state.load_baseline() if self.state.baseline_path.exists() else None
        if (current_baseline[0] if current_baseline else None) != plan.baseline_id:
            raise StalePlanError("baseline changed after planning")
        run_id = self.state.new_run_id()
        self.state.acquire_lock(run_id)
        leave_lock = False
        journal = {
            "version": JOURNAL_VERSION,
            "pair_id": self.state.pair_id,
            "run_id": run_id,
            "plan": plan.to_dict(),
            "state": "PLANNED",
            "created_ns": time.time_ns(),
            "operations": [{"spec": op.to_dict(), "state": "PLANNED"} for op in plan.operations],
        }
        try:
            self.state.write_journal(journal)
            fault.hit("after_journal_creation")
            journal["state"] = "STARTED"
            self.state.write_journal(journal)
            for index, op in enumerate(plan.operations):
                self._execute_operation(run_id, op, journal, index, fault)
                fault.hit("after_operation")
            fault.hit("before_verification")
            left, right = self._snapshots()
            if not _snapshots_equivalent(left, right):
                raise RecoveryRequired("post-apply verification failed; baseline not advanced")
            journal["state"] = "VERIFIED"
            self.state.write_journal(journal)
            fault.hit("after_verification")
            baseline_id = self.state.write_baseline(left, run_id, fault=fault)
            fault.hit("before_journal_finalize")
            journal["state"] = "COMMITTED"
            journal["baseline_id"] = baseline_id
            journal["committed_ns"] = time.time_ns()
            self.state.write_journal(journal)
            self._cleanup_run_artifacts(run_id, plan)
            return {"status": "COMMITTED", "run_id": run_id, "plan_id": plan.id, "operations": len(plan.operations), "baseline_id": baseline_id}
        except InjectedCrash:
            leave_lock = True
            raise
        finally:
            if not leave_lock:
                self.state.release_lock(run_id, force=False)

    def recover(self, *, fault: FaultInjector | None = None) -> dict[str, Any]:
        self.init()
        incompletes = self.state.incomplete_journals()
        if not incompletes:
            self._clear_or_refuse_orphan_lock()
            return {"status": "CLEAN", "recovered": False}
        if len(incompletes) != 1:
            raise RecoveryRequired("multiple incomplete journals require manual intervention")
        path, journal = incompletes[0]
        run_id = journal["run_id"]
        self._break_matching_stale_lock(run_id)
        self.state.acquire_lock(run_id)
        fault = fault or FaultInjector()
        leave_lock = False
        try:
            try:
                plan = Plan.from_dict(journal["plan"])
            except (KeyError, TypeError, ValueError) as exc:
                raise StateError("journal contains an invalid plan") from exc
            expected_specs = [op.to_dict() for op in plan.operations]
            actual_specs = [item.get("spec") for item in journal.get("operations", []) if isinstance(item, dict)]
            if actual_specs != expected_specs or len(actual_specs) != len(journal.get("operations", [])):
                raise StateError("journal operation list does not match embedded plan")
            allowed_states = {"PLANNED", "STARTED", "MATERIALIZED", "RENAMED", "VERIFIED"}
            if any(item.get("state") not in allowed_states for item in journal["operations"]):
                raise StateError("journal contains an invalid operation state")
            baseline = self.state.load_baseline() if self.state.baseline_path.exists() else None
            if baseline:
                raw = read_checked_json(self.state.baseline_path)
                if raw.get("committed_run_id") == run_id:
                    left, right = self._snapshots()
                    if not _snapshots_equivalent(left, right):
                        raise RecoveryRequired("baseline says committed but trees diverge")
                    journal["state"] = "COMMITTED"
                    journal["baseline_id"] = baseline[0]
                    self.state.write_journal(journal)
                    self._cleanup_run_artifacts(run_id, plan)
                    return {"status": "FINALIZED", "recovered": True, "run_id": run_id, "baseline_id": baseline[0]}
            current_baseline_id = baseline[0] if baseline else None
            if current_baseline_id != plan.baseline_id:
                raise RecoveryRequired("baseline changed independently since interrupted run")
            for index, item in enumerate(journal["operations"]):
                op = Operation.from_dict(item["spec"])
                if self._operation_satisfied(op):
                    item["state"] = "VERIFIED"
                    self.state.write_journal(journal)
                    continue
                self._execute_operation(run_id, op, journal, index, fault)
            left, right = self._snapshots()
            if not _snapshots_equivalent(left, right):
                raise RecoveryRequired("recovery operations completed but trees are not equivalent")
            journal["state"] = "VERIFIED"
            self.state.write_journal(journal)
            baseline_id = self.state.write_baseline(left, run_id, fault=fault)
            fault.hit("before_journal_finalize")
            journal["state"] = "COMMITTED"
            journal["baseline_id"] = baseline_id
            self.state.write_journal(journal)
            self._cleanup_run_artifacts(run_id, plan)
            return {"status": "RECOVERED", "recovered": True, "run_id": run_id, "baseline_id": baseline_id}
        except InjectedCrash:
            leave_lock = True
            raise
        finally:
            if not leave_lock:
                self.state.release_lock(run_id, force=False)

    def _clear_or_refuse_orphan_lock(self) -> None:
        if not self.state.lock_path.exists():
            return
        try:
            data = json.loads(self.state.lock_path.read_text("utf-8"))
        except Exception as exc:
            raise RecoveryRequired("malformed orphan lock requires manual inspection") from exc
        pid = data.get("pid")
        if isinstance(pid, int) and pid != os.getpid() and _pid_alive(pid):
            raise LockError(f"pair is actively locked by pid {pid}")
        self.state.release_lock(force=True)

    def _break_matching_stale_lock(self, run_id: str) -> None:
        if not self.state.lock_path.exists():
            return
        try:
            data = json.loads(self.state.lock_path.read_text("utf-8"))
        except Exception as exc:
            raise RecoveryRequired("malformed lock blocks automatic recovery") from exc
        if data.get("run_id") != run_id:
            raise LockError("another run holds the pair lock")
        pid = data.get("pid")
        if isinstance(pid, int) and pid != os.getpid() and _pid_alive(pid):
            raise LockError(f"run {run_id} still appears active as pid {pid}")
        self.state.release_lock(force=True)

    def _root(self, side: str) -> Path:
        if side == "LEFT":
            return self.left
        if side == "RIGHT":
            return self.right
        raise StateError(f"invalid side {side!r}")

    def _operation_satisfied(self, op: Operation) -> bool:
        actual = _inspect(self._root(op.side), op.path)
        if op.action == "DELETE":
            return actual is None
        if op.action == "RENAME":
            if not _matches(actual, op.expected_after):
                return False
            if not op.source_side or not op.source_path:
                return False
            return _inspect(self._root(op.source_side), op.source_path) is None
        return _matches(actual, op.expected_after)

    def _execute_operation(self, run_id: str, op: Operation, journal: dict[str, Any], index: int, fault: FaultInjector) -> None:
        item = journal["operations"][index]
        item["state"] = "STARTED"
        self.state.write_journal(journal)
        if self._operation_satisfied(op):
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        dest_root = self._root(op.side)
        dest = confined_path(dest_root, op.path)
        source = None
        if op.source_side and op.source_path:
            source = confined_path(self._root(op.source_side), op.source_path)
            source_now = _inspect(self._root(op.source_side), op.source_path)
            if not _matches(source_now, op.expected_source):
                if not (op.action == "RENAME" and source_now is None and _matches(_inspect(dest_root, op.path), op.expected_after)):
                    raise StalePlanError(f"source precondition changed: {op.source_side}:{op.source_path}")

        actual_before = _inspect(dest_root, op.path)
        backup = _backup_path(dest, run_id, op.id)

        if op.action == "RENAME" and source is not None:
            source_now = _inspect(self._root(op.source_side), op.source_path)
            if _matches(actual_before, op.expected_after) and _matches(source_now, op.expected_source):
                source.unlink()
                fsync_dir(source.parent)
                item["state"] = "VERIFIED"
                self.state.write_journal(journal)
                return
            if _matches(actual_before, op.expected_after) and source_now is None:
                item["state"] = "VERIFIED"
                self.state.write_journal(journal)
                return

        if backup.exists() or backup.is_symlink():
            if op.expected_before is None or not _matches(_inspect_path(backup, op.path), op.expected_before):
                raise RecoveryRequired(f"unexpected recovery backup for {op.path}")
        elif not _matches(actual_before, op.expected_before):
            raise StalePlanError(f"destination precondition changed: {op.side}:{op.path}")

        if op.action == "DELETE":
            if actual_before is None and (backup.exists() or backup.is_symlink()):
                pass
            elif actual_before is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.replace(dest, backup)
                fsync_dir(dest.parent)
            item["state"] = "RENAMED"
            self.state.write_journal(journal)
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        if op.action == "RENAME":
            assert source is not None
            dest.parent.mkdir(parents=True, exist_ok=True)
            _capture_destination(dest_root, op.path, dest, backup, op.expected_before)
            if not _matches(_inspect(self._root(op.source_side), op.source_path), op.expected_source):
                raise StalePlanError(f"rename source changed: {op.source_path}")
            if dest.exists() or dest.is_symlink():
                raise StalePlanError(f"rename destination appeared during commit: {op.path}")
            source_entry = _inspect(self._root(op.source_side), op.source_path)
            fault.hit("before_rename")
            try:
                if source_entry and source_entry.kind == "file":
                    os.link(source, dest)
                elif source_entry and source_entry.kind == "symlink":
                    os.symlink(os.readlink(source), dest, target_is_directory=False)
                else:
                    raise RecoveryRequired("only file/symlink exact renames are supported")
            except FileExistsError as exc:
                raise StalePlanError(f"rename destination appeared during commit: {op.path}") from exc
            except OSError as exc:
                raise RecoveryRequired(f"safe no-clobber rename unavailable for {op.path}: {exc}") from exc
            fault.hit("after_rename")
            source.unlink()
            fsync_dir(source.parent)
            fsync_dir(dest.parent)
            item["state"] = "RENAMED"
            self.state.write_journal(journal)
            if not self._operation_satisfied(op):
                raise RecoveryRequired(f"rename verification failed: {op.path}")
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        if op.action == "MKDIR":
            if actual_before is None:
                dest.mkdir(parents=True, exist_ok=False)
                fsync_dir(dest.parent)
            if not self._operation_satisfied(op):
                raise RecoveryRequired(f"mkdir verification failed: {op.path}")
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        if op.action == "SYMLINK":
            assert source is not None and op.expected_source is not None
            target = op.expected_source.get("link_target")
            if not isinstance(target, str):
                raise StateError("symlink operation missing link target")
            dest.parent.mkdir(parents=True, exist_ok=True)
            _capture_destination(dest_root, op.path, dest, backup, op.expected_before)
            temp = _temp_path(dest, run_id, op.id)
            temp.unlink(missing_ok=True)
            os.symlink(target, temp, target_is_directory=False)
            item["state"] = "MATERIALIZED"
            self.state.write_journal(journal)
            fault.hit("after_temp_write")
            if dest.exists() or dest.is_symlink():
                temp.unlink(missing_ok=True)
                raise StalePlanError(f"destination changed during symlink commit: {op.path}")
            fault.hit("before_rename")
            try:
                os.symlink(target, dest, target_is_directory=False)
            except FileExistsError as exc:
                temp.unlink(missing_ok=True)
                raise StalePlanError(f"destination changed during symlink commit: {op.path}") from exc
            temp.unlink(missing_ok=True)
            fault.hit("after_rename")
            fsync_dir(dest.parent)
            if not self._operation_satisfied(op):
                raise RecoveryRequired(f"symlink verification failed: {op.path}")
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        if op.action == "COPY":
            assert source is not None and op.expected_source is not None
            fault.hit("before_source_read")
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = _temp_path(dest, run_id, op.id)
            if temp.exists() or temp.is_symlink():
                temp.unlink(missing_ok=True)
            _copy_verified(source, temp, op.expected_source, fault)
            item["state"] = "MATERIALIZED"
            self.state.write_journal(journal)
            fault.hit("after_temp_write")
            _capture_destination(dest_root, op.path, dest, backup, op.expected_before)
            if not _matches(_inspect(self._root(op.source_side), op.source_path), op.expected_source):
                raise StalePlanError(f"source changed before commit: {op.source_path}")
            fault.hit("before_rename")
            try:
                os.link(temp, dest)
            except FileExistsError as exc:
                raise StalePlanError(f"destination appeared during commit: {op.path}") from exc
            except OSError as exc:
                raise RecoveryRequired(f"safe no-clobber file install unavailable for {op.path}: {exc}") from exc
            temp.unlink(missing_ok=True)
            fault.hit("after_rename")
            item["state"] = "RENAMED"
            self.state.write_journal(journal)
            fault.hit("before_directory_fsync")
            fsync_dir(dest.parent)
            if not self._operation_satisfied(op):
                raise RecoveryRequired(f"copy verification failed: {op.path}")
            item["state"] = "VERIFIED"
            self.state.write_journal(journal)
            return

        raise StateError(f"unsupported operation {op.action}")

    def _cleanup_run_artifacts(self, run_id: str, plan: Plan) -> None:
        for op in plan.operations:
            dest = confined_path(self._root(op.side), op.path)
            for artifact in (_temp_path(dest, run_id, op.id), _backup_path(dest, run_id, op.id), _backup_path(dest, run_id, op.id + "r")):
                _remove_artifact(artifact)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _entry_from_lstat(path: Path, logical_path: str) -> Entry:
    st = os.lstat(path)
    mode = None if os.name == "nt" else stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        target = os.readlink(path)
        digest = hashlib.sha256(target.encode("utf-8", "surrogatepass")).hexdigest()
        return Entry(logical_path, "symlink", digest, len(target.encode("utf-8", "surrogatepass")), mode, target)
    if stat.S_ISDIR(st.st_mode):
        return Entry(logical_path, "dir", None, 0, mode, None)
    if stat.S_ISREG(st.st_mode):
        digest, size = file_sha256(path)
        return Entry(logical_path, "file", digest, size, mode, None)
    raise PathSafetyError(f"unsupported filesystem object: {logical_path}")


def _inspect(root: Path, rel: str) -> Entry | None:
    path = confined_path(root, validate_relpath(rel))
    try:
        return _entry_from_lstat(path, rel)
    except FileNotFoundError:
        return None


def _inspect_path(path: Path, logical_path: str) -> Entry | None:
    try:
        return _entry_from_lstat(path, logical_path)
    except FileNotFoundError:
        return None


def _matches(actual: Entry | None, expected: dict[str, Any] | None) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    e = Entry.from_dict(expected)
    return actual.kind == e.kind and actual.digest == e.digest and actual.size == e.size and actual.link_target == e.link_target and (e.mode is None or actual.mode == e.mode)


def _snapshots_equivalent(left: Snapshot, right: Snapshot) -> bool:
    if set(left.entries) != set(right.entries):
        return False
    for path in left.entries:
        if not left.entries[path].content_equal(right.entries[path]):
            return False
    return True


def _artifact_name(dest: Path, marker: str, run_id: str, op_id: str) -> str:
    safe = dest.name or "root"
    return f".{safe}.ferrosync-{marker}-{run_id[:12]}-{op_id}"


def _temp_path(dest: Path, run_id: str, op_id: str) -> Path:
    return dest.parent / _artifact_name(dest, "tmp", run_id, op_id)


def _backup_path(dest: Path, run_id: str, op_id: str) -> Path:
    return dest.parent / _artifact_name(dest, "backup", run_id, op_id)


def _capture_destination(root: Path, rel: str, dest: Path, backup: Path, expected_before: dict[str, Any] | None) -> None:
    if backup.exists() or backup.is_symlink():
        if not _matches(_inspect_path(backup, rel), expected_before):
            raise RecoveryRequired(f"backup does not match planned destination state: {rel}")
        return
    actual = _inspect(root, rel)
    if not _matches(actual, expected_before):
        raise StalePlanError(f"destination changed after plan: {rel}")
    if actual is not None:
        os.replace(dest, backup)
        fsync_dir(dest.parent)
        if not _matches(_inspect_path(backup, rel), expected_before):
            raise StalePlanError(f"captured destination differs from plan: {rel}")


def _copy_verified(source: Path, temp: Path, expected: dict[str, Any], fault: FaultInjector) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    src_fd = None
    dst_fd = None
    h = hashlib.sha256()
    total = 0
    try:
        src_fd = os.open(source, flags)
        dst_fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        before = os.fstat(src_fd)
        while True:
            chunk = os.read(src_fd, 1024 * 1024)
            if not chunk:
                break
            fault.hit("during_copy")
            total += len(chunk)
            h.update(chunk)
            view = memoryview(chunk)
            while view:
                n = os.write(dst_fd, view)
                view = view[n:]
        os.fsync(dst_fd)
        fault.hit("after_file_fsync")
        after = os.fstat(src_fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise StalePlanError(f"source changed while copying: {source}")
        if h.hexdigest() != expected.get("digest") or total != expected.get("size"):
            raise StalePlanError(f"copied bytes do not match planned source: {source}")
        mode = expected.get("mode")
        if mode is not None and os.name != "nt":
            os.chmod(temp, int(mode))
    except BaseException:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        if src_fd is not None:
            os.close(src_fd)
        if dst_fd is not None:
            os.close(dst_fd)


def _remove_artifact(path: Path) -> None:
    try:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _unexpected_artifacts(root: Path) -> list[str]:
    out: list[str] = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        rel_dir = Path(directory).relative_to(root)
        if rel_dir.parts and rel_dir.parts[0] == ".ferrosync":
            dirs[:] = []
            continue
        for name in list(dirs) + files:
            if ".ferrosync-tmp-" in name or ".ferrosync-backup-" in name:
                out.append(str((Path(directory) / name).relative_to(root)))
    return out
