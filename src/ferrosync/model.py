from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .util import sha256_json, validate_relpath

STATE_VERSION = 1
JOURNAL_VERSION = 1
PLAN_VERSION = 1


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    digest: str | None = None
    size: int = 0
    mode: int | None = None
    link_target: str | None = None

    def identity(self) -> tuple[str, str | None, int, str | None]:
        return (self.kind, self.digest, self.size, self.link_target)

    def content_equal(self, other: "Entry | None") -> bool:
        return other is not None and self.identity() == other.identity()

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "digest": self.digest,
            "size": self.size,
            "mode": self.mode,
            "link_target": self.link_target,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Entry":
        if not isinstance(d, dict):
            raise ValueError("entry must be an object")
        path = validate_relpath(d["path"])
        kind = d["kind"]
        if kind not in {"file", "dir", "symlink"}:
            raise ValueError("unsupported entry kind")
        digest = d.get("digest")
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("invalid content digest")
        size = int(d.get("size", 0))
        if size < 0:
            raise ValueError("negative entry size")
        link_target = d.get("link_target")
        if kind == "symlink" and not isinstance(link_target, str):
            raise ValueError("symlink missing target")
        if kind != "symlink" and link_target is not None:
            raise ValueError("non-symlink has link target")
        return cls(path=path, kind=kind, digest=digest, size=size, mode=d.get("mode"), link_target=link_target)


@dataclass
class Snapshot:
    entries: dict[str, Entry]

    def to_dict(self) -> dict[str, Any]:
        return {p: self.entries[p].to_dict() for p in sorted(self.entries)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Snapshot":
        if not isinstance(d, dict):
            raise ValueError("snapshot must be an object")
        out: dict[str, Entry] = {}
        for p, v in d.items():
            vp = validate_relpath(p)
            entry = Entry.from_dict(v)
            if entry.path != vp:
                raise ValueError("snapshot key/path mismatch")
            out[vp] = entry
        return cls(out)


@dataclass(frozen=True)
class Operation:
    id: str
    action: str
    side: str
    path: str
    source_side: str | None = None
    source_path: str | None = None
    expected_before: dict[str, Any] | None = None
    expected_source: dict[str, Any] | None = None
    expected_after: dict[str, Any] | None = None
    destructive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "side": self.side,
            "path": self.path,
            "source_side": self.source_side,
            "source_path": self.source_path,
            "expected_before": self.expected_before,
            "expected_source": self.expected_source,
            "expected_after": self.expected_after,
            "destructive": self.destructive,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Operation":
        return cls(**d)


@dataclass(frozen=True)
class Conflict:
    id: str
    kind: str
    path: str
    left: dict[str, Any] | None
    right: dict[str, Any] | None
    baseline: dict[str, Any] | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "left": self.left,
            "right": self.right,
            "baseline": self.baseline,
            "detail": self.detail,
        }


@dataclass
class Plan:
    operations: list[Operation] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    baseline_id: str | None = None
    version: int = PLAN_VERSION

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    def logical_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "baseline_id": self.baseline_id,
            "operations": [op.to_dict() for op in self.operations],
            "conflicts": [c.to_dict() for c in self.conflicts],
        }

    @property
    def id(self) -> str:
        return sha256_json(self.logical_dict())

    def to_dict(self) -> dict[str, Any]:
        d = self.logical_dict()
        d["plan_id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Plan":
        operations = [Operation.from_dict(v) for v in d.get("operations", [])]
        conflicts = [Conflict(**v) for v in d.get("conflicts", [])]
        if len({op.id for op in operations}) != len(operations):
            raise ValueError("duplicate operation id")
        for op in operations:
            payload = op.to_dict().copy(); supplied = payload.pop("id")
            if supplied != sha256_json(payload)[:20]:
                raise ValueError("operation identity mismatch")
        if len({c.id for c in conflicts}) != len(conflicts):
            raise ValueError("duplicate conflict id")
        for c in conflicts:
            payload = c.to_dict().copy(); supplied = payload.pop("id")
            if supplied != sha256_json(payload)[:20]:
                raise ValueError("conflict identity mismatch")
        plan = cls(
            operations=operations,
            conflicts=conflicts,
            baseline_id=d.get("baseline_id"),
            version=int(d.get("version", 0)),
        )
        if plan.version != PLAN_VERSION or d.get("plan_id") not in (None, plan.id):
            raise ValueError("unsupported or corrupt plan")
        return plan
