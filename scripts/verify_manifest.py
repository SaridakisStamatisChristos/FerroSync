#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"evidence"/"MANIFEST.sha256"
EXCLUDED_PARTS={".git","__pycache__",".pytest_cache","build","dist",".venv","venv"}


def authoritative_files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel=p.relative_to(ROOT)
        if rel == Path("evidence/MANIFEST.sha256"):
            continue
        if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if p.suffix in {".pyc", ".pyo"}:
            continue
        yield rel,p


def digest(rel: Path, path: Path) -> str:
    # Verify the canonical Git blob rather than checkout-materialized bytes.
    # This keeps evidence stable across CRLF/LF working-tree policies.
    try:
        data=subprocess.check_output(
            ["git", "show", f":{rel.as_posix()}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        data=path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def render():
    return "".join(f"{digest(rel,p)}  {rel.as_posix()}\n" for rel,p in authoritative_files())


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); args=ap.parse_args()
    current=render()
    if args.write:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(current, encoding="utf-8")
        print(f"wrote {MANIFEST} with {len(current.splitlines())} entries")
        return 0
    if not MANIFEST.exists():
        print("manifest missing")
        return 1
    expected=MANIFEST.read_text(encoding="utf-8")
    if expected != current:
        print("manifest mismatch")
        return 1
    print(f"manifest verified: {len(current.splitlines())} files")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
