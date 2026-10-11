"""Filesystem confinement, hashing, fsync, and checked-state helpers."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import PathSafetyError, StateError

STATE_MAX_BYTES = 16 * 1024 * 1024


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        while True:
            chunk = os.read(fd, chunk_size)
            if not chunk:
                break
            total += len(chunk)
            h.update(chunk)
    finally:
        os.close(fd)
    return h.hexdigest(), total


def validate_relpath(rel: str) -> str:
    if not isinstance(rel, str) or not rel or "\x00" in rel:
        raise PathSafetyError("relative path must be a non-empty string without NUL")
    if "\\" in rel:
        rel = rel.replace("\\", "/")
    p = PurePosixPath(rel)
    if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts):
        raise PathSafetyError(f"unsafe relative path: {rel!r}")
    first = p.parts[0]
    if ":" in first or first.startswith("//"):
        raise PathSafetyError(f"unsafe platform path: {rel!r}")
    return p.as_posix()


def confined_path(root: Path, rel: str, *, allow_leaf_symlink: bool = True) -> Path:
    rel = validate_relpath(rel)
    root = root.resolve(strict=True)
    candidate = root.joinpath(*PurePosixPath(rel).parts)
    current = root
    parts = PurePosixPath(rel).parts
    for idx, part in enumerate(parts[:-1] if allow_leaf_symlink else parts):
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(st.st_mode):
            raise PathSafetyError(f"symlink parent escapes confinement policy: {current}")
    try:
        common = os.path.commonpath([str(root), str(candidate.absolute())])
    except ValueError as exc:
        raise PathSafetyError("path is on a different drive") from exc
    if os.path.normcase(common) != os.path.normcase(str(root)):
        raise PathSafetyError(f"path escapes root: {rel}")
    return candidate


def fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600, fault=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode) if hasattr(os, "fchmod") else None
        with os.fdopen(fd, "wb", closefd=True) as f:
            if fault:
                fault.hit("during_baseline_write")
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        fsync_dir(path.parent)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def write_checked_json(path: Path, payload: dict[str, Any], *, fault=None) -> None:
    envelope = {"payload": payload, "checksum": sha256_json(payload)}
    atomic_write_bytes(path, canonical_json(envelope) + b"\n", fault=fault)


def read_checked_json(path: Path, *, max_bytes: int = STATE_MAX_BYTES) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise
    if size > max_bytes:
        raise StateError(f"state file too large: {path}")
    try:
        raw = path.read_bytes()
        env = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(f"invalid state file: {path}") from exc
    if not isinstance(env, dict) or set(env) != {"payload", "checksum"}:
        raise StateError(f"invalid state envelope: {path}")
    payload = env["payload"]
    if not isinstance(payload, dict) or not isinstance(env["checksum"], str):
        raise StateError(f"invalid state envelope types: {path}")
    if sha256_json(payload) != env["checksum"]:
        raise StateError(f"checksum mismatch: {path}")
    return payload
