from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import SyncPair
from .errors import ConflictError, FerroSyncError, InjectedCrash


def _emit(value, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
    elif isinstance(value, dict):
        for k, v in value.items():
            print(f"{k}: {v}")
    else:
        print(value)


def _pair(args) -> SyncPair:
    return SyncPair.open(Path(args.left), Path(args.right))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ferrosync", description="Deterministic, crash-safe bidirectional filesystem synchronization")
    p.add_argument("--version", action="version", version=f"ferrosync {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def roots(name, help_text):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("left")
        sp.add_argument("right")
        sp.add_argument("--json", action="store_true", help="emit machine-readable JSON")
        return sp

    init = roots("init", "initialize pair metadata without synchronizing user data")
    init.add_argument("--ignore", action="append", default=[], help="additional deterministic ignore pattern")
    roots("plan", "compute an inspectable dry-run plan")
    roots("sync", "plan and apply a safe synchronization")
    roots("status", "show baseline, pending changes, conflicts, and recovery state")
    roots("verify", "verify state, journal health, and tree equivalence without mutation")
    roots("recover", "recover one interrupted synchronization run")
    roots("conflicts", "list persisted conflict reports")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        pair = _pair(args)
        if args.command == "init":
            _emit(pair.init(args.ignore), args.json)
            return 0
        if args.command == "plan":
            plan = pair.plan()
            _emit(plan.to_dict(), args.json)
            return 2 if plan.has_conflicts else 0
        if args.command == "sync":
            _emit(pair.sync(), args.json)
            return 0
        if args.command == "status":
            _emit(pair.status(), args.json)
            return 0
        if args.command == "verify":
            result = pair.verify()
            _emit(result, args.json)
            return 0 if result["ok"] else 3
        if args.command == "recover":
            _emit(pair.recover(), args.json)
            return 0
        if args.command == "conflicts":
            reports = []
            if pair.state.conflict_dir.exists():
                for path in sorted(pair.state.conflict_dir.glob("*.json")):
                    reports.append(str(path))
            _emit({"reports": reports}, args.json)
            return 0
        return 1
    except ConflictError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": "conflict", "message": str(exc)}, sort_keys=True))
        else:
            print(f"conflict: {exc}", file=sys.stderr)
        return 2
    except InjectedCrash as exc:
        print(f"injected crash: {exc}", file=sys.stderr)
        return 99
    except (FerroSyncError, OSError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": exc.__class__.__name__, "message": str(exc)}, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
