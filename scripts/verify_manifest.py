#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def render():
    return "".join(f"{digest(p)}  {rel.as_posix()}\n" for rel,p in authoritative_files())


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
