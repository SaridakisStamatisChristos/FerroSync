# Development

FerroSync targets Python 3.10+ and intentionally uses the standard library at runtime.

```bash
make static
make test
```

The test suite is `unittest` so a clean interpreter can run the correctness gates without downloading test dependencies. Tests cover planner tables, real filesystem integration, crash injection/recovery, adversarial state/path cases, a separate one-path reference oracle, and seeded randomized sequences.

The fault injector uses `FERROSYNC_CRASH_AT=LABEL[:N]` or `FaultInjector("LABEL[:N]")`. Declared labels are documented in `evidence/REQUIREMENTS.md` and exercised by `tests/test_crash_recovery.py`.

A failure discovered during falsification must be retained in `evidence/FAILURE_REPAIR_LEDGER.md` with reproducer, violated invariant, earliest invalidated phase, repair, regression, and reverification.
