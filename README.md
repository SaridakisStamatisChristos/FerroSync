# FerroSync

**A deterministic, crash-safe bidirectional filesystem synchronization engine.**

FerroSync reconciles two independently changing directory trees without treating either side as permanently authoritative. It computes an inspectable plan before user-tree mutation, uses SHA-256 content identity, refuses ambiguous conflicts, journals every mutation, advances the baseline only after verified completion, and can recover an interrupted run.

> Status: experimental systems software. The repository is evidence-driven and heavily tested, but it is not a sandbox against a process with arbitrary write access to both synchronized trees.

## Core guarantees

- No automatic overwrite when both sides independently changed incompatibly.
- Destructive propagation is baseline-gated; absence alone is never evidence for deletion.
- Identical trees + baseline + config produce the same logical plan.
- Symlinks are copied as symlinks and never followed during traversal.
- Persistent state and journals are versioned and checksummed.
- Baseline commit happens only after operation completion and post-sync equivalence verification.
- Recovery is explicit and idempotent for supported interruption boundaries.
- A portable namespace policy rejects NFC+casefold collisions rather than guessing across OSes.

## Install

```bash
python -m pip install .
ferrosync --version
```

Python 3.10+ is required. FerroSync has no runtime third-party dependencies.

## Quick start

```bash
mkdir left right
ferrosync init left right
ferrosync plan left right
ferrosync sync left right
ferrosync status left right
ferrosync verify left right
```

If an interrupted run is detected:

```bash
ferrosync recover left right
```

Machine-readable output is available with `--json` after each subcommand, for example:

```bash
ferrosync plan left right --json
```

A conflict causes `sync` to leave both user versions in place and write a checksummed conflict report under `LEFT/.ferrosync/conflicts/`.

## Library API

```python
from ferrosync import SyncPair

pair = SyncPair.open("left", "right")
plan = pair.plan()
if not plan.has_conflicts:
    result = pair.apply(plan)
```

`apply()` revalidates the persisted baseline and operation preconditions; a plan is not a capability to bypass stale-state checks.

## State ownership

`LEFT/.ferrosync/` is the metadata anchor for the ordered pair `(LEFT, RIGHT)`. This does **not** make LEFT authoritative for user data. Root order is part of persistent pair identity so the state location and recovery journal are unambiguous.

## Development

```bash
make verify
```

Equivalent dependency-free commands:

```bash
PYTHONPATH=src python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/verify_manifest.py
```

See `docs/` for the algorithm, journal, recovery, filesystem semantics, security model, operations, benchmarks, and limitations. Evidence closure is under `evidence/`.
