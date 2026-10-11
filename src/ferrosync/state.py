from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import LockError, StateError
from .model import JOURNAL_VERSION, STATE_VERSION, Snapshot
from .util import atomic_write_bytes, canonical_json, read_checked_json, sha256_json, write_checked_json


class StateStore:
    def __init__(self, left: Path, right: Path):
        self.left = Path(left).resolve(strict=True)
        self.right = Path(right).resolve(strict=True)
        self.root = self.left / ".ferrosync"
        self.pair_path = self.root / "state.json"
        self.baseline_path = self.root / "baseline.json"
        self.journal_dir = self.root / "journal"
        self.lock_path = self.root / "locks" / "pair.lock"
        self.conflict_dir = self.root / "conflicts"

    @property
    def pair_id(self) -> str:
        return sha256_json({"left": str(self.left), "right": str(self.right)})[:24]

    def ensure_layout(self, ignore_patterns: list[str]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.conflict_dir.mkdir(parents=True, exist_ok=True)
        if self.pair_path.exists():
            self.validate_pair()
            return
        payload = {
            "version": STATE_VERSION,
            "pair_id": self.pair_id,
            "left": str(self.left),
            "right": str(self.right),
            "ignore_patterns": list(ignore_patterns),
            "created_ns": time.time_ns(),
        }
        write_checked_json(self.pair_path, payload)

    def validate_pair(self) -> dict[str, Any]:
        p = read_checked_json(self.pair_path)
        if p.get("version") != STATE_VERSION:
            raise StateError("unsupported pair state version")
        if p.get("pair_id") != self.pair_id or p.get("left") != str(self.left) or p.get("right") != str(self.right):
            raise StateError("root identity does not match persisted synchronization pair")
        patterns = p.get("ignore_patterns")
        if (not isinstance(patterns, list) or len(patterns) > 1024 or
                not all(isinstance(x, str) and 0 < len(x) <= 1024 and "\x00" not in x for x in patterns)):
            raise StateError("invalid ignore pattern state")
        return p

    def ignore_patterns(self, defaults: tuple[str, ...]) -> tuple[str, ...]:
        if not self.pair_path.exists():
            return defaults
        return tuple(self.validate_pair()["ignore_patterns"])

    def load_baseline(self) -> tuple[str, Snapshot] | None:
        if not self.baseline_path.exists():
            return None
        p = read_checked_json(self.baseline_path)
        if p.get("version") != STATE_VERSION:
            raise StateError("unsupported baseline version")
        if p.get("pair_id") != self.pair_id:
            raise StateError("baseline belongs to a different synchronization pair")
        snap_raw = p.get("snapshot")
        if not isinstance(snap_raw, dict):
            raise StateError("invalid baseline snapshot")
        try:
            snapshot = Snapshot.from_dict(snap_raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise StateError("invalid baseline snapshot entries") from exc
        expected_id = sha256_json({"pair_id": self.pair_id, "snapshot": snapshot.to_dict()})
        if p.get("baseline_id") != expected_id:
            raise StateError("baseline identity mismatch")
        return expected_id, snapshot

    def write_baseline(self, snapshot: Snapshot, run_id: str, *, fault=None) -> str:
        baseline_id = sha256_json({"pair_id": self.pair_id, "snapshot": snapshot.to_dict()})
        payload = {
            "version": STATE_VERSION,
            "pair_id": self.pair_id,
            "baseline_id": baseline_id,
            "committed_run_id": run_id,
            "snapshot": snapshot.to_dict(),
            "committed_ns": time.time_ns(),
        }
        if fault:
            fault.hit("before_baseline_write")
        write_checked_json(self.baseline_path, payload, fault=fault)
        if fault:
            fault.hit("after_baseline_replace")
        return baseline_id

    def acquire_lock(self, run_id: str) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json({"version": 1, "run_id": run_id, "pid": os.getpid(), "created_ns": time.time_ns()}) + b"\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(self.lock_path, flags, 0o600)
        except FileExistsError as exc:
            raise LockError(f"sync pair is locked: {self.lock_path}") from exc
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

    def release_lock(self, run_id: str | None = None, *, force: bool = False) -> None:
        if not self.lock_path.exists():
            return
        if not force and run_id is not None:
            try:
                data = json.loads(self.lock_path.read_text("utf-8"))
            except Exception as exc:
                raise StateError("malformed lock file") from exc
            if data.get("run_id") != run_id:
                raise LockError("refusing to release another run's lock")
        self.lock_path.unlink(missing_ok=True)

    def new_run_id(self) -> str:
        return uuid.uuid4().hex

    def journal_path(self, run_id: str) -> Path:
        if not run_id.isalnum():
            raise StateError("invalid run id")
        return self.journal_dir / f"{run_id}.json"

    def write_journal(self, payload: dict[str, Any]) -> None:
        if payload.get("version") != JOURNAL_VERSION:
            raise StateError("unsupported journal version")
        write_checked_json(self.journal_path(payload["run_id"]), payload)

    def load_journal(self, path: Path) -> dict[str, Any]:
        p = read_checked_json(path)
        if p.get("version") != JOURNAL_VERSION or p.get("pair_id") != self.pair_id:
            raise StateError(f"unsupported or foreign journal: {path}")
        return p

    def incomplete_journals(self) -> list[tuple[Path, dict[str, Any]]]:
        if not self.journal_dir.exists():
            return []
        out: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(self.journal_dir.glob("*.json")):
            p = self.load_journal(path)
            if p.get("state") not in {"COMMITTED", "ABORTED"}:
                out.append((path, p))
        return out

    def record_conflicts(self, plan_id: str, conflicts: list[dict[str, Any]]) -> Path:
        self.conflict_dir.mkdir(parents=True, exist_ok=True)
        path = self.conflict_dir / f"{plan_id}.json"
        write_checked_json(path, {"version": 1, "pair_id": self.pair_id, "plan_id": plan_id, "conflicts": conflicts})
        return path
