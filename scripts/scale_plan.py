#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from pathlib import Path

from ferrosync.model import Entry, Snapshot
from ferrosync.planner import build_plan


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=1_000_000)
    ap.add_argument("--output")
    args=ap.parse_args()
    if args.paths < 1:
        raise SystemExit("--paths must be positive")
    entries={}
    digest="0"*64
    for i in range(args.paths):
        path=f"d{i//1000:06d}/f{i:09d}"
        entries[path]=Entry(path,"file",digest=digest,size=1,mode=0o644)
    snap=Snapshot(entries)
    t=time.perf_counter(); plan=build_plan(snap,snap,snap,"baseline"); elapsed=time.perf_counter()-t
    out={
        "paths": args.paths,
        "seconds": elapsed,
        "operations": len(plan.operations),
        "conflicts": len(plan.conflicts),
        "deterministic_noop": len(plan.operations)==0 and len(plan.conflicts)==0,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "note": "shared immutable snapshot objects; measures planner path/classification scale, not filesystem scanning",
    }
    text=json.dumps(out, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text+"\n", encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
