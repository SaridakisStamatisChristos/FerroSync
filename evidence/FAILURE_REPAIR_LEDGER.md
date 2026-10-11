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

## F-004 — GitHub-hosted matrix jobs failed before runner assignment

- **Phase discovered:** VERIFY / remote CI
- **Reproducer/evidence:** GitHub Actions run `38154026963`, attempt 1, all six jobs (Ubuntu/macOS/Windows × Python 3.10/3.13). Each completed `failure` with `runner_id=0`, empty `steps`, and no downloadable job log.
- **Observed behavior:** no repository command, test, build, package, or smoke step executed.
- **Affected requirement:** R24 cross-platform execution evidence and R27 remote CI gate.
- **Root-cause classification:** external hosted-runner/pre-execution availability; no product-code failure was observed. Exact account-side cause is not exposed by the available connector metadata.
- **Earliest invalidated phase:** VERIFY evidence only; CONTRACT/SPEC/implementation are not invalidated by a job that never executed.
- **Changed evidence path:** checked GitHub public status (Actions reported operational) and performed one failed-jobs retry as attempt 2 to falsify a transient runner-assignment hypothesis.
- **Reverification:** attempt 2 reproduced the identical result on all six jobs: failure before runner assignment, no steps/logs.
- **Loop rule:** no further unchanged retry is permitted under R7 without a changed external premise (for example account Actions/billing/runner availability).
- **Status:** BLOCKED / UNVERIFIED cross-platform CI; local gates remain VERIFIED.

## F-005 — cross-platform adversarial tests encoded filesystem-path assumptions

- **Phase discovered:** VERIFY / remote CI after hosted runners became available.
- **Reproducer/evidence:** GitHub Actions run `38154408061`, retry attempt after the repository became public. Ubuntu lanes passed, while macOS/Windows executed the suite and exposed two adversarial-test portability defects.
- **Observed behavior:** `test_casefold_collision_fails_safe` could not reliably create both `A.txt` and `a.txt` on case-insensitive filesystems; `test_permission_error_during_scan_is_rejected` compared an uncanonicalized temporary path to the canonicalized `SyncPair.left` root, so the injected denial was bypassed on macOS `/var` -> `/private/var` and normalized Windows paths.
- **Violated requirement:** R24 cross-platform verification quality; the product invariant itself was not falsified by these two failures.
- **Root cause:** test harness assumed Linux-like namespace/path identity rather than testing the logical namespace and canonicalized scan root directly.
- **Earliest invalidated phase:** VERIFY test harness only.
- **Repair:** drive the case-collision invariant through synthetic `Snapshot` entries so the logical portable-namespace policy is tested independently of host filesystem case semantics; compare the injected permission-denial path against `SyncPair.left` after `Path.resolve()`.
- **Runtime source impact:** none.
- **Reverification:** PENDING full Linux/macOS/Windows × Python 3.10/3.13 matrix.
- **Status:** REPAIR APPLIED / REVERIFY PENDING.
