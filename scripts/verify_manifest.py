#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "MANIFEST.sha256"
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv"}


def authoritative_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if rel == Path("evidence/MANIFEST.sha256"):
            continue
        if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        yield rel, path


def _git_blob(rel: Path) -> bytes | None:
    try:
        return subprocess.check_output(
            ["git", "show", f":{rel.as_posix()}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def _is_utf8_text(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def digest_candidates(rel: Path, path: Path) -> set[str]:
    payloads = [path.read_bytes()]
    git_data = _git_blob(rel)
    if git_data is not None:
        payloads.append(git_data)

    # Git checkouts can materialize text with CRLF on Windows even when the
    # repository's authoritative content was hashed with LF. Accept only that
    # reversible EOL representation difference; all other byte changes fail.
    for data in tuple(payloads):
        if _is_utf8_text(data) and b"\r\n" in data:
            payloads.append(data.replace(b"\r\n", b"\n"))

    return {hashlib.sha256(data).hexdigest() for data in payloads}


def canonical_digest(rel: Path, path: Path) -> str:
    data = _git_blob(rel)
    if data is None:
        data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def render() -> str:
    return "".join(
        f"{canonical_digest(rel, path)}  {rel.as_posix()}\n"
        for rel, path in authoritative_files()
    )


def parse_manifest(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        digest, sep, rel = line.partition("  ")
        if not sep or len(digest) != 64 or not rel or rel in out:
            raise ValueError(f"invalid manifest line: {line!r}")
        out[rel] = digest
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if args.write:
        current = render()
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(current, encoding="utf-8")
        print(f"wrote {MANIFEST} with {len(current.splitlines())} entries")
        return 0

    if not MANIFEST.exists():
        print("manifest missing")
        return 1

    try:
        expected = parse_manifest(MANIFEST.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"manifest invalid: {exc}")
        return 1

    files = list(authoritative_files())
    actual_paths = {rel.as_posix() for rel, _ in files}
    expected_paths = set(expected)
    if actual_paths != expected_paths:
        missing = sorted(actual_paths - expected_paths)
        stale = sorted(expected_paths - actual_paths)
        print(f"manifest path-set mismatch: missing={missing} stale={stale}")
        return 1

    mismatches: list[str] = []
    for rel, path in files:
        key = rel.as_posix()
        if expected[key] not in digest_candidates(rel, path):
            mismatches.append(key)

    if mismatches:
        print("manifest digest mismatch: " + ", ".join(mismatches))
        return 1

    print(f"manifest verified: {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
