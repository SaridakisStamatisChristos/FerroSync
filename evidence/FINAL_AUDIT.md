# Final adversarial audit

This audit is authority-aware: local execution evidence is closed where observed, and cross-platform claims are closed only by an observed hosted CI run on committed repository state. The earlier runner-assignment blocker and subsequent cross-platform test/evidence failures are retained in `FAILURE_REPAIR_LEDGER.md`; none are rewritten as successes.

## Falsification questions

1. **Can an independent edit disappear silently?** Tested modify/modify and stale-plan paths preserve versions/refuse. No counterexample in the declared test scope.
2. **Can a delete propagate without baseline evidence?** Planner requires a baseline entry and unchanged peer; tested.
3. **Can a conflict overwrite one side?** `sync` records conflict metadata and stops before user-tree mutation; tested.
4. **Can enumeration order change the plan?** Sorted scan/plan plus reversed-input deterministic test; no.
5. **Can a stale plan overwrite a newer file?** Destination precondition and final-window race tests refuse without overwriting the newer destination; no counterexample in the declared trust boundary.
6. **Can a crash advance the baseline prematurely?** 15-boundary injection shows baseline advances only after verification; no counterexample.
7. **Can recovery apply an operation twice destructively?** Outcome inspection + idempotence test; no counterexample.
8. **Can a temp file become authoritative accidentally?** Temp names are excluded from scanning and verify flags unexpected artifacts; baseline comes from post-sync logical scan.
9. **Can a corrupt journal be interpreted as valid?** Truncation/checksum test fails closed.
10. **Can a symlink escape the root?** Parent-symlink confinement test fails closed on hosts where symlink creation is available; scanner never follows links.
11. **Can a crafted path escape the root?** `..`, absolute, and drive-like forms are rejected; persisted entries are validated.
12. **Can a source changing during copy produce an accepted hybrid file?** Copy hashes bytes and rechecks source identity; a final-window source mutation prevents baseline commit, and post-run equivalence is mandatory. Source disappearance during scan found F-001 and was repaired.
13. **Can two initial conflicting files be treated as identical history?** Initial different-content collision is a conflict; tested.
14. **Can ambiguous rename detection destroy information?** Only unique exact-content matches auto-rename; ambiguous cases fall back to pathwise conservative behavior/conflict.
15. **Can case-only rename break on Windows/macOS?** Portable NFC+casefold collisions fail closed rather than auto-rename; the logical namespace test is host-filesystem independent.
16. **Can repeated sync with no changes mutate anything?** Baseline bytes remain identical and no journal is created on clean no-op; tested.
17. **Can repeated crash/recover cycles diverge?** Repeated recovery idempotence tested for declared boundaries; no counterexample.
18. **Can ignored files enter the baseline accidentally?** Ignore-baseline test says no.
19. **Can state corruption silently reset history?** Baseline checksum/version/root-identity mismatch fails closed; tested.
20. **Does documentation claim stronger cross-platform guarantees than evidence supports?** No; Windows/macOS durability differences and Windows symlink-creation privilege limitations remain explicit.

## Cross-platform CI closure

GitHub Actions run `38156641062` completed successfully on commit `cd2c5b45f59667f015371724a7470279b838f6ca`.

Observed green matrix:

- Ubuntu + Python 3.10 and 3.13;
- macOS + Python 3.10 and 3.13;
- Windows + Python 3.10 and 3.13.

Every lane passed:

- compile/static gate;
- unit, integration, adversarial, property, and crash/recovery suite;
- evidence-manifest verification;
- wheel build;
- installed CLI smoke.

Windows runners skipped the symlink-creation tests where host privilege/developer mode did not permit creating symlinks; that limitation remains explicit and is not promoted into a Windows symlink guarantee.

## Residual risks / limitations

- Arbitrary hostile concurrent writers are outside the security contract; there is no portable filesystem compare-and-swap primitive for every final rename race.
- Directory `fsync`, rename durability, metadata fidelity, case behavior, and symlink privileges vary by filesystem/OS; identical durability semantics are not claimed.
- No comparative performance claim is made.
- The successful matrix is strong engineering evidence, not a formal proof and not a production-deployment soak.

## Final verdict

**R7 ACCEPTANCE GATES CLOSED for the declared v0.1 experimental scope.**

Synthesis, local verification, package installation, crash/property/adversarial campaigns, evidence integrity, and the declared Linux/macOS/Windows CI matrix have been observed green. Production readiness beyond that declared scope remains **NOT CLAIMED**.
