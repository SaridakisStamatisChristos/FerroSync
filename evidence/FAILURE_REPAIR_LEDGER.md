# Failure / repair ledger

## F-001 — cached `DirEntry.stat()` could hide source disappearance

- **Phase discovered:** FALSIFY
- **Reproducer:** `test_source_disappearing_during_scan_is_rejected`
- **Observed behavior:** mocked source deletion immediately after hashing did not raise; the scan could accept an entry that vanished because `DirEntry.stat()` may return cached metadata.
- **Violated invariant:** H6/H19 change-during-scan defense; stale input must not be accepted as a stable snapshot.
- **Root cause:** post-hash verification reused the directory-entry stat API instead of forcing a fresh filesystem stat.
- **Earliest invalidated phase:** GENERATE (`scanner.py` implementation).
- **Repair:** replaced initial/post-hash `DirEntry.stat(follow_symlinks=False)` usage with fresh `os.stat(path, follow_symlinks=False)` calls; retained before/after size/mtime/inode comparison.
- **Regression:** the original adversarial test now passes.
- **Reverification:** complete 34-test suite passed after repair; randomized/property and crash suites rerun.
- **Status:** CLOSED / VERIFIED.

## F-002 — fresh venv packaging path attempted network-dependent tool upgrade

- **Phase discovered:** PACKAGE
- **Reproducer:** create clean venv, `pip install --upgrade pip setuptools wheel` in sandbox without DNS/network.
- **Observed behavior:** package-index retries timed out; no product code was executed by that failed attempt.
- **Violated requirement:** none in FerroSync; package evidence path unavailable in environment.
- **Root cause:** sandbox network restriction, not repository packaging metadata.
- **Earliest invalidated phase:** PACKAGE evidence method only.
- **Repair/evidence change:** did not repeat unchanged network action. Used system-installed `setuptools 82.0.1`/`wheel 0.46.3` with `pip wheel --no-build-isolation`, then installed the produced wheel into a fresh venv with `--no-index --find-links`.
- **Reverification:** wheel built; `ferrosync 0.1.0`; installed CLI sync + verify smoke passed.
- **Status:** CLOSED for local package evidence; GitHub CI package lanes remain to be observed.

## F-003 — no-clobber hardening patch temporarily displaced execution method

- **Phase discovered:** REPAIR/REVERIFY
- **Reproducer:** full unit suite immediately after no-clobber hardening.
- **Observed behavior:** `SyncPair._execute_operation` was absent because an edit boundary matched the earlier `RENAME` branch inside `_operation_satisfied`; sync tests failed with `AttributeError`.
- **Violated invariant:** repository integration/build integrity, not a released runtime semantic.
- **Root cause:** overly broad source-edit range during repair.
- **Earliest invalidated phase:** GENERATE/INTEGRATE for `engine.py`.
- **Repair:** reconstructed `_operation_satisfied` and `_execute_operation` as separate class methods, retained the no-clobber file/symlink/rename logic, then reran targeted race tests followed by the complete suite.
- **Regression/reverification:** targeted bidirectional/race tests passed; final local suite passed 47/47.
- **Status:** CLOSED / VERIFIED.
