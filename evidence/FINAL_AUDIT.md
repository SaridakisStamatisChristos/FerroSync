# Final adversarial audit

This audit is intentionally authority-aware: local execution evidence is closed where observed. GitHub Actions run `38154026963` was inspected twice; both attempts failed before any hosted runner was assigned, so cross-platform execution remains unverified rather than being misreported as a product pass or failure.

## Falsification questions

1. **Can an independent edit disappear silently?** Tested modify/modify and stale-plan paths preserve versions/refuse. No counterexample in local suite.
2. **Can a delete propagate without baseline evidence?** Planner requires a baseline entry and unchanged peer; tested.
3. **Can a conflict overwrite one side?** `sync` records conflict metadata and stops before user-tree mutation; tested.
4. **Can enumeration order change the plan?** Sorted scan/plan plus reversed-input deterministic test; no.
5. **Can a stale plan overwrite a newer file?** Destination precondition and final-window race tests refuse without overwriting the newer destination; no counterexample in the declared trust boundary.
6. **Can a crash advance the baseline prematurely?** 15-boundary injection shows baseline advances only after verification; no counterexample.
7. **Can recovery apply an operation twice destructively?** Outcome inspection + idempotence test; no counterexample.
8. **Can a temp file become authoritative accidentally?** Temp names are excluded from scanning and verify flags unexpected artifacts; baseline comes from post-sync logical scan.
9. **Can a corrupt journal be interpreted as valid?** Truncation/checksum test fails closed.
10. **Can a symlink escape the root?** Parent-symlink confinement test fails closed; scanner never follows links.
11. **Can a crafted path escape the root?** `..`, absolute, drive-like forms rejected; persisted entries validated.
12. **Can a source changing during copy produce an accepted hybrid file?** copy hashes bytes and rechecks source identity; a final-window source mutation prevents baseline commit, and post-run equivalence is mandatory. Source disappearance during scan found F-001 and was repaired.
13. **Can two initial conflicting files be treated as identical history?** initial different-content collision is a conflict; tested.
14. **Can ambiguous rename detection destroy information?** only unique exact-content matches auto-rename; ambiguous cases fall back to pathwise conservative behavior/conflict.
15. **Can case-only rename break on Windows/macOS?** portable NFC+casefold collisions fail closed rather than auto-rename.
16. **Can repeated sync with no changes mutate anything?** baseline bytes remain identical and no journal is created on clean no-op; tested.
17. **Can repeated crash/recover cycles diverge?** repeated recovery idempotence tested for declared boundaries; no counterexample.
18. **Can ignored files enter the baseline accidentally?** ignore baseline test says no.
19. **Can state corruption silently reset history?** baseline checksum/version/root identity mismatch fails closed; tested.
20. **Does documentation claim stronger cross-platform guarantees than evidence supports?** no; Windows/macOS durability and symlink limitations are explicit.

## Residual risks / unresolved evidence

- GitHub Actions cross-platform execution is externally blocked: run `38154026963`, attempts 1 and 2, created all six Linux/macOS/Windows × Python 3.10/3.13 jobs, but each ended with `runner_id=0`, an empty step list, and no job log. The public GitHub status page reported Actions operational when the retry was initiated, so no GitHub-wide incident was used to excuse the gap.
- Arbitrary hostile concurrent writers are outside the security contract; there is no portable filesystem compare-and-swap primitive for every final rename race.
- No comparative performance claim is made.

## Final verdict

**CONDITIONAL — synthesis, local verification, package installation, crash/property/adversarial campaigns, and manifest closure are complete; the hard cross-platform CI execution gate remains UNVERIFIED because GitHub hosted runners never started.**

This is not a code-failure verdict. It is an evidence-availability verdict. Production-readiness must remain conditional until at least one full Linux/macOS/Windows matrix run executes the committed gates successfully.
