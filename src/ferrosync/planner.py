"""Deterministic three-way synchronization planning and exact rename detection."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable
import unicodedata

from .model import Conflict, Entry, Operation, Plan, Snapshot
from .util import sha256_json


def _d(e: Entry | None):
    return e.to_dict() if e else None


def classify(current: Entry | None, baseline: Entry | None) -> str:
    if baseline is None:
        return "ADDED" if current is not None else "UNCHANGED"
    if current is None:
        return "DELETED"
    if current.kind != baseline.kind:
        return "TYPE_CHANGED"
    if current.content_equal(baseline):
        if current.mode != baseline.mode:
            return "METADATA_CHANGED"
        return "UNCHANGED"
    return "MODIFIED"


def _conflict(kind: str, path: str, left: Entry | None, right: Entry | None, base: Entry | None, detail: str) -> Conflict:
    payload = {"kind": kind, "path": path, "left": _d(left), "right": _d(right), "baseline": _d(base), "detail": detail}
    return Conflict(id=sha256_json(payload)[:20], **payload)


def _op(action: str, side: str, path: str, *, source_side=None, source_path=None, before=None, source=None, after=None, destructive=False) -> Operation:
    payload = {
        "action": action,
        "side": side,
        "path": path,
        "source_side": source_side,
        "source_path": source_path,
        "expected_before": _d(before),
        "expected_source": _d(source),
        "expected_after": _d(after),
        "destructive": destructive,
    }
    return Operation(id=sha256_json(payload)[:20], **payload)


def _unique_file_renames(current: Snapshot, baseline: Snapshot) -> dict[str, str]:
    deleted: dict[tuple, list[str]] = defaultdict(list)
    added: dict[tuple, list[str]] = defaultdict(list)
    for path, base in baseline.entries.items():
        if base.kind not in {"file", "symlink"}:
            continue
        if path not in current.entries:
            deleted[base.identity()].append(path)
    for path, cur in current.entries.items():
        if cur.kind not in {"file", "symlink"}:
            continue
        if path not in baseline.entries:
            added[cur.identity()].append(path)
    out: dict[str, str] = {}
    for identity, old_paths in deleted.items():
        new_paths = added.get(identity, [])
        if len(old_paths) == 1 and len(new_paths) == 1:
            out[old_paths[0]] = new_paths[0]
    return out


def _sort_ops(ops: Iterable[Operation]) -> list[Operation]:
    # Parent creation/copy first, child deletions before parent deletions.
    priority = {"MKDIR": 0, "RENAME": 1, "COPY": 2, "SYMLINK": 2, "CHMOD": 3, "DELETE": 4}
    def key(op: Operation):
        depth = op.path.count("/")
        if op.action == "DELETE":
            depth = -depth
        return (priority.get(op.action, 9), depth, op.side, op.path, op.id)
    return sorted(ops, key=key)


def build_plan(left: Snapshot, right: Snapshot, baseline: Snapshot | None, baseline_id: str | None = None) -> Plan:
    base = baseline or Snapshot({})
    ops: list[Operation] = []
    conflicts: list[Conflict] = []

    # Portable namespace policy: paths that collapse under NFC+casefold are
    # never auto-created. This prevents plans valid on Linux from becoming
    # destructive or unrepresentable on common Windows/macOS filesystems.
    namespace: dict[str, set[str]] = defaultdict(set)
    for path in set(base.entries) | set(left.entries) | set(right.entries):
        namespace[unicodedata.normalize("NFC", path).casefold()].add(path)
    blocked_paths: set[str] = set()
    for key, group in sorted(namespace.items()):
        if len(group) > 1:
            names = sorted(group)
            blocked_paths.update(names)
            for path in names:
                conflicts.append(_conflict("case-collision", path, left.entries.get(path), right.entries.get(path), base.entries.get(path), "portable namespace collision: " + ", ".join(names)))

    left_renames = _unique_file_renames(left, base) if baseline else {}
    right_renames = _unique_file_renames(right, base) if baseline else {}
    consumed: set[str] = set()

    # Resolve only unambiguous exact-content file/symlink renames.
    for old in sorted(set(left_renames) | set(right_renames)):
        if old in blocked_paths or left_renames.get(old) in blocked_paths or right_renames.get(old) in blocked_paths:
            continue
        lnew = left_renames.get(old)
        rnew = right_renames.get(old)
        b = base.entries.get(old)
        lold = left.entries.get(old)
        rold = right.entries.get(old)
        if lnew and rnew:
            if lnew == rnew:
                consumed.update({old, lnew})
                continue
            conflicts.append(_conflict("rename/rename-divergence", old, left.entries.get(lnew), right.entries.get(rnew), b, f"LEFT->{lnew}, RIGHT->{rnew}"))
            consumed.update({old, lnew, rnew})
            continue
        if lnew:
            if rold is not None and rold.content_equal(b):
                if lnew in right.entries and not right.entries[lnew].content_equal(left.entries[lnew]):
                    conflicts.append(_conflict("rename/target-collision", lnew, left.entries[lnew], right.entries[lnew], None, f"rename from {old}"))
                else:
                    ops.append(_op("RENAME", "RIGHT", lnew, source_side="RIGHT", source_path=old, before=right.entries.get(lnew), source=rold, after=left.entries[lnew], destructive=True))
                consumed.update({old, lnew})
            else:
                conflicts.append(_conflict("rename/modify", old, left.entries.get(lnew), rold, b, f"LEFT renamed to {lnew} while RIGHT changed/deleted"))
                consumed.update({old, lnew})
        elif rnew:
            if lold is not None and lold.content_equal(b):
                if rnew in left.entries and not left.entries[rnew].content_equal(right.entries[rnew]):
                    conflicts.append(_conflict("rename/target-collision", rnew, left.entries[rnew], right.entries[rnew], None, f"rename from {old}"))
                else:
                    ops.append(_op("RENAME", "LEFT", rnew, source_side="LEFT", source_path=old, before=left.entries.get(rnew), source=lold, after=right.entries[rnew], destructive=True))
                consumed.update({old, rnew})
            else:
                conflicts.append(_conflict("rename/modify", old, lold, right.entries.get(rnew), b, f"RIGHT renamed to {rnew} while LEFT changed/deleted"))
                consumed.update({old, rnew})

    paths = sorted(set(base.entries) | set(left.entries) | set(right.entries))
    for path in paths:
        if path in consumed or path in blocked_paths:
            continue
        l = left.entries.get(path)
        r = right.entries.get(path)
        b = base.entries.get(path)
        lc, rc = classify(l, b), classify(r, b)

        if baseline is None:
            if l is None and r is None:
                continue
            if l is not None and r is None:
                action = "MKDIR" if l.kind == "dir" else ("SYMLINK" if l.kind == "symlink" else "COPY")
                ops.append(_op(action, "RIGHT", path, source_side="LEFT", source_path=path, before=None, source=l, after=l))
                continue
            if r is not None and l is None:
                action = "MKDIR" if r.kind == "dir" else ("SYMLINK" if r.kind == "symlink" else "COPY")
                ops.append(_op(action, "LEFT", path, source_side="RIGHT", source_path=path, before=None, source=r, after=r))
                continue
            if l and r and l.content_equal(r):
                continue
            conflicts.append(_conflict("initial-collision", path, l, r, None, "pre-existing paths have no common baseline"))
            continue

        if lc == "UNCHANGED" and rc == "UNCHANGED":
            continue
        if l and r and l.content_equal(r):
            # Same content reached independently; metadata may differ but content safety is satisfied.
            continue

        if lc in {"TYPE_CHANGED"} or rc in {"TYPE_CHANGED"}:
            conflicts.append(_conflict("type-change", path, l, r, b, f"LEFT={lc}, RIGHT={rc}; conservative manual resolution"))
            continue

        if lc == "DELETED" and rc == "UNCHANGED":
            ops.append(_op("DELETE", "RIGHT", path, before=r, source=None, after=None, destructive=True))
            continue
        if rc == "DELETED" and lc == "UNCHANGED":
            ops.append(_op("DELETE", "LEFT", path, before=l, source=None, after=None, destructive=True))
            continue
        if lc == "DELETED" and rc == "DELETED":
            continue
        if lc == "DELETED" and rc != "UNCHANGED":
            conflicts.append(_conflict("delete/modify", path, l, r, b, f"LEFT deleted, RIGHT={rc}"))
            continue
        if rc == "DELETED" and lc != "UNCHANGED":
            conflicts.append(_conflict("modify/delete", path, l, r, b, f"LEFT={lc}, RIGHT deleted"))
            continue

        if lc != "UNCHANGED" and rc == "UNCHANGED":
            assert l is not None
            action = "MKDIR" if l.kind == "dir" else ("SYMLINK" if l.kind == "symlink" else "COPY")
            ops.append(_op(action, "RIGHT", path, source_side="LEFT", source_path=path, before=r, source=l, after=l, destructive=r is not None))
            continue
        if rc != "UNCHANGED" and lc == "UNCHANGED":
            assert r is not None
            action = "MKDIR" if r.kind == "dir" else ("SYMLINK" if r.kind == "symlink" else "COPY")
            ops.append(_op(action, "LEFT", path, source_side="RIGHT", source_path=path, before=l, source=r, after=r, destructive=l is not None))
            continue

        # Both changed and are not content-equal.
        kind = "add/add" if b is None else "modify/modify"
        conflicts.append(_conflict(kind, path, l, r, b, f"LEFT={lc}, RIGHT={rc}"))

    # Ensure conflicts deterministically suppress operations touching the same logical path.
    conflict_paths = {c.path for c in conflicts}
    ops = [op for op in ops if op.path not in conflict_paths and (op.source_path or "") not in conflict_paths]
    conflicts.sort(key=lambda c: (c.path, c.kind, c.id))
    return Plan(operations=_sort_ops(ops), conflicts=conflicts, baseline_id=baseline_id)
