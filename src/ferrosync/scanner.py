from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
from pathlib import Path, PurePosixPath

from .errors import PathSafetyError
from .model import Entry, Snapshot
from .util import file_sha256, validate_relpath

DEFAULT_IGNORES = (".ferrosync", ".ferrosync/**", "*.ferrosync-tmp-*", "*.ferrosync-backup-*", "*.tmp", "build", "build/**")


def _ignored(rel: str, patterns: tuple[str, ...]) -> bool:
    rel = rel.replace("\\", "/")
    base = PurePosixPath(rel).name
    for pat in patterns:
        if fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(base, pat):
            return True
        if pat.endswith("/**") and (rel == pat[:-3] or rel.startswith(pat[:-2])):
            return True
    return False


def _mode_bits(st_mode: int) -> int | None:
    if os.name == "nt":
        return None
    return stat.S_IMODE(st_mode)


def scan_tree(root: Path, patterns: tuple[str, ...] = DEFAULT_IGNORES) -> Snapshot:
    root = Path(root)
    if not root.exists() or not root.is_dir() or root.is_symlink():
        raise PathSafetyError(f"sync root must be an existing real directory: {root}")
    entries: dict[str, Entry] = {}

    def walk(directory: Path, prefix: str = "") -> None:
        try:
            children = list(os.scandir(directory))
        except OSError as exc:
            raise PathSafetyError(f"cannot scan {directory}: {exc}") from exc
        children.sort(key=lambda e: e.name)
        for child in children:
            rel = f"{prefix}/{child.name}" if prefix else child.name
            rel = validate_relpath(rel)
            if _ignored(rel, patterns):
                continue
            try:
                st = os.stat(child.path, follow_symlinks=False)
            except OSError as exc:
                raise PathSafetyError(f"cannot stat {rel}: {exc}") from exc
            if stat.S_ISLNK(st.st_mode):
                try:
                    target = os.readlink(child.path)
                except OSError as exc:
                    raise PathSafetyError(f"cannot read symlink {rel}: {exc}") from exc
                digest = hashlib.sha256(target.encode("utf-8", "surrogatepass")).hexdigest()
                entries[rel] = Entry(rel, "symlink", digest=digest, size=len(target.encode("utf-8", "surrogatepass")), mode=_mode_bits(st.st_mode), link_target=target)
            elif stat.S_ISDIR(st.st_mode):
                entries[rel] = Entry(rel, "dir", digest=None, size=0, mode=_mode_bits(st.st_mode))
                walk(Path(child.path), rel)
            elif stat.S_ISREG(st.st_mode):
                try:
                    digest, size = file_sha256(Path(child.path))
                except OSError as exc:
                    raise PathSafetyError(f"cannot hash {rel}: {exc}") from exc
                # Re-stat after hashing; changes are detected rather than accepting a hybrid scan.
                try:
                    # Fresh syscall: DirEntry.stat() is allowed to cache and can hide
                    # a disappearance/change that occurred during hashing.
                    st2 = os.stat(child.path, follow_symlinks=False)
                except OSError as exc:
                    raise PathSafetyError(f"source disappeared while scanning {rel}: {exc}") from exc
                if (st.st_size, st.st_mtime_ns, st.st_ino) != (st2.st_size, st2.st_mtime_ns, st2.st_ino):
                    raise PathSafetyError(f"source changed while scanning: {rel}")
                entries[rel] = Entry(rel, "file", digest=digest, size=size, mode=_mode_bits(st2.st_mode))
            else:
                raise PathSafetyError(f"unsupported filesystem object at {rel}")

    walk(root)
    return Snapshot(entries)
