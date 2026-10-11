#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import InjectedCrash
from ferrosync.faults import FaultInjector
from ferrosync.scanner import scan_tree


def timed(fn, repeats=1):
    samples=[]
    result=None
    for _ in range(repeats):
        t=time.perf_counter(); result=fn(); samples.append(time.perf_counter()-t)
    return {"seconds_min": min(samples), "seconds_median": statistics.median(samples), "repeats": repeats}, result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--output")
    args=ap.parse_args()
    count=200 if args.quick else 2000
    size=4096 if args.quick else 65536
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); l=base/"left"; r=base/"right"; l.mkdir(); r.mkdir()
        payload=(b"ferrosync" * ((size//9)+1))[:size]
        for i in range(count):
            (l/f"f{i:06d}.bin").write_bytes(payload + i.to_bytes(4,"little"))
        scan_obs,_=timed(lambda: scan_tree(l), 3 if args.quick else 5)
        p=SyncPair.open(l,r)
        sync_obs,sync_result=timed(lambda: p.sync())
        unchanged_obs,plan=timed(lambda: p.plan(), 3 if args.quick else 5)
        # Rename-heavy sample: 10% exact-content renames.
        rename_n=max(1,count//10)
        for i in range(rename_n):
            os.rename(l/f"f{i:06d}.bin", l/f"renamed-{i:06d}.bin")
        rename_obs,rename_plan=timed(lambda: p.plan())
        # Return to synchronized state, then measure one recovery path.
        p.sync()
        (l/"recovery.bin").write_bytes(payload)
        try:
            p.sync(fault=FaultInjector("after_rename"))
        except InjectedCrash:
            pass
        recovery_obs,recovery_result=timed(lambda: p.recover())
        state_size=sum(x.stat().st_size for x in p.state.root.rglob("*") if x.is_file())
        out={
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "workload": {"files": count, "bytes_per_file": size},
            "scan": scan_obs,
            "initial_sync": {**sync_obs, "operations": sync_result["operations"]},
            "unchanged_plan": {**unchanged_obs, "operations": len(plan.operations), "conflicts": len(plan.conflicts)},
            "rename_plan": {**rename_obs, "renamed_files": rename_n, "operations": len(rename_plan.operations), "conflicts": len(rename_plan.conflicts)},
            "recovery": {**recovery_obs, "status": recovery_result["status"]},
            "state_bytes": state_size,
            "claim": "observational only; no comparative superiority claim",
        }
    text=json.dumps(out, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text+"\n", encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
