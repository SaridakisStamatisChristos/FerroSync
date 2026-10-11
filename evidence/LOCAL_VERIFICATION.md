# Local verification record

Environment: Python 3.13.5, x86_64 Linux 6.18.44, glibc 2.41.

## Static + tests

Command:

```bash
PYTHONPATH=src python -m compileall -q src tests scripts
PYTHONPATH=src python -m unittest discover -s tests -v
```

Observed after F-001 repair: **47 test methods passed**. The randomized campaign includes **40 fixed seeds × 12 one-sided mutation/sync rounds = 480 rounds**. The independent one-path reference test exhausts 27 `(baseline,left,right)` content-state combinations. Crash recovery exercises 15 named interruption boundaries plus repeated recovery idempotence.

## Scale

`evidence/scale_local.json`: 1,000,000 synthetic logical paths, deterministic no-op plan, 0 operations, 0 conflicts, ~6.70 s in this environment. Peak RSS recorded by the process was ~919,044 KiB. This is not a filesystem-scan benchmark.

## Quick benchmark

`evidence/benchmark_local.json` records a 200 × 4 KiB-file workload: repeated scan, initial sync, unchanged plan, 20 exact-content renames, recovery, and state size. Results are observations, not comparative claims.

## Package / installed CLI

The successful offline evidence path was:

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
python -m venv /mnt/data/ferrosync-venv
/mnt/data/ferrosync-venv/bin/python -m pip install --no-index --find-links dist ferrosync
/mnt/data/ferrosync-venv/bin/ferrosync --version
```

Observed wheel SHA-256 from build output: `8910285618cfdf754c0a767948585e153a301560e99300e90eb14fddcf45ed1f`. Installed version reported `ferrosync 0.1.0`; an installed-CLI one-file sync and verify smoke passed.

## Manifest negative test

After generating `evidence/MANIFEST.sha256`, `README.md` was modified temporarily. `python scripts/verify_manifest.py` returned failure (`manifest mismatch`). Restoring the exact bytes returned the verifier to success. The manifest was then regenerated after this evidence note, so the committed manifest covers the final local tree.
