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
- **Reverification:** local wheel build + clean-venv sync/verify smoke passed; GitHub Actions run `38156641062` also built the wheel and passed installed CLI smoke on all six declared matrix lanes.
- **Status:** CLOSED / VERIFIED.

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
- **Reverification:** attempt 2 reproduced the identical result on all six jobs: failure before runner assignment, no steps/logs. The repository owner then reported that private-repository Actions minutes were exhausted and changed the repository to public. With that external premise changed, hosted runners executed normally; subsequent runs produced real platform evidence.
- **Closure evidence:** run `38156641062` completed successfully across all six declared matrix lanes.
- **Status:** CLOSED / EXTERNAL BLOCKER RESOLVED.

## F-005 — cross-platform adversarial tests encoded filesystem-path assumptions

- **Phase discovered:** VERIFY / remote CI after hosted runners became available.
- **Reproducer/evidence:** GitHub Actions run `38154408061`, retry attempt after the repository became public. Ubuntu lanes passed, while macOS/Windows executed the suite and exposed two adversarial-test portability defects.
- **Observed behavior:** `test_casefold_collision_fails_safe` could not reliably create both `A.txt` and `a.txt` on case-insensitive filesystems; `test_permission_error_during_scan_is_rejected` compared an uncanonicalized temporary path to the canonicalized `SyncPair.left` root, so the injected denial was bypassed on macOS `/var` -> `/private/var` and normalized Windows paths.
- **Violated requirement:** R24 cross-platform verification quality; the product invariant itself was not falsified by these two failures.
- **Root cause:** test harness assumed Linux-like namespace/path identity rather than testing the logical namespace and canonicalized scan root directly.
- **Earliest invalidated phase:** VERIFY test harness only.
- **Repair:** drive the case-collision invariant through synthetic `Snapshot` entries so the logical portable-namespace policy is tested independently of host filesystem case semantics; compare the injected permission-denial path against `SyncPair.left` after `Path.resolve()`.
- **Runtime source impact:** none.
- **Reverification:** GitHub Actions run `38155668644` executed all six Linux/macOS/Windows × Python 3.10/3.13 test suites; all six product/adversarial/property/crash test steps passed. Windows then exposed the independent manifest portability issue recorded as F-006.
- **Status:** CLOSED / VERIFIED for the test-harness repair.

## F-006 — evidence manifest depended on host checkout line endings

- **Phase discovered:** VERIFY / remote CI.
- **Reproducer/evidence:** GitHub Actions run `38155668644`. Linux and macOS completed tests, manifest verification, wheel build, and installed CLI smoke successfully. Both Windows lanes passed the full 47-test suite, then failed only at `python scripts/verify_manifest.py` with `manifest mismatch`.
- **Observed behavior:** authoritative source bytes were hashed from the working tree; Windows checkout line-ending conversion can materialize text files differently from the LF bytes used to generate the committed manifest.
- **Affected requirement:** R27 evidence-manifest verification on every supported CI lane.
- **Root cause:** the verifier hashed checkout-materialized bytes rather than canonical repository blobs, so evidence depended on host checkout conversion.
- **Earliest invalidated phase:** MANIFEST / EVIDENCE tooling only.
- **Repair attempt 1:** added a repository-wide LF `.gitattributes` policy. Run `38155953536` showed that this broadened the mismatch because historical blobs with pre-existing line endings were rematerialized differently on checkout.
- **Final repair:** remove the checkout-policy workaround and make `scripts/verify_manifest.py` hash canonical Git index blobs (`git show :path`) when available, falling back to working-tree bytes only outside a Git checkout. The manifest therefore attests repository content rather than platform-specific checkout materialization.
- **Runtime source impact:** none.
- **Reverification:** the canonical-blob attempt improved Linux/macOS behavior but Windows still exposed EOL representation variance, leading to F-008. Final closure is provided by run `38156641062` after the F-008 repair.
- **Status:** CLOSED via superseding F-008 repair.

## F-007 — manually refreshed manifest carried a stale ledger digest

- **Phase discovered:** REVERIFY / evidence closure.
- **Reproducer/evidence:** GitHub Actions run `38156182408`. All completed product test steps were green, but manifest verification failed because `evidence/MANIFEST.sha256` contained an incorrect SHA-256 for the current `evidence/FAILURE_REPAIR_LEDGER.md` blob.
- **Observed behavior:** the canonical-blob verifier correctly rejected the evidence set on Linux/macOS; the remaining Windows lanes were therefore not used as acceptance evidence.
- **Affected requirement:** R27 evidence-manifest integrity only.
- **Root cause:** manifest refresh error while recording the preceding repair; the verifier itself correctly failed closed.
- **Earliest invalidated phase:** MANIFEST / EVIDENCE.
- **Repair:** recompute the ledger digest from the exact committed UTF-8 content and refresh only the authoritative manifest/ledger evidence pair.
- **Runtime source impact:** none.
- **Reverification:** corrected digest was incorporated before the later F-008 verifier repair; run `38156641062` subsequently passed evidence verification on every matrix lane.
- **Status:** CLOSED / VERIFIED.

## F-008 — Windows Git/checkout EOL representation still differed from stored evidence hashes

- **Phase discovered:** REVERIFY / cross-platform evidence.
- **Reproducer/evidence:** GitHub Actions run `38156394425`. Linux and macOS lanes passed the full tests, manifest, wheel build, and installed CLI smoke. Both Windows lanes passed all 47 tests, then failed only at manifest verification.
- **Observed behavior:** replacing working-tree hashing with `git show :path` was sufficient on Linux/macOS but still did not make the verifier representation-independent on the Windows runners.
- **Affected requirement:** R27 evidence-manifest portability only.
- **Root-cause classification:** platform-dependent text EOL materialization/plumbing representation; no product or test failure was observed.
- **Earliest invalidated phase:** MANIFEST / EVIDENCE.
- **Repair:** verifier now checks each expected digest against both working-tree and Git-blob payloads and, for valid UTF-8 text only, the reversible CRLF-to-LF normalization of those payloads. The committed manifest remains a SHA-256 file inventory; arbitrary non-EOL byte changes still fail closed, and path-set mismatches are reported explicitly.
- **Runtime source impact:** none.
- **Reverification:** GitHub Actions run `38156641062` completed successfully on commit `cd2c5b45f59667f015371724a7470279b838f6ca`. All six Linux/macOS/Windows × Python 3.10/3.13 jobs passed the full test suite, manifest verification, wheel build, and installed CLI smoke.
- **Status:** CLOSED / VERIFIED.
