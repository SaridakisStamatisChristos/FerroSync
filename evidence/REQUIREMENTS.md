# Requirement coverage ledger

Statuses in this repository use `VERIFIED | PARTIAL | UNVERIFIED | FAILED | N/A`. Local evidence below refers to the campaign revision before GitHub CI; cross-platform CI is tracked separately in `CLAIMS.md`/`FINAL_AUDIT.md`.

| ID | Requirement / invariant | Implementation surface | Acceptance evidence | State |
|---|---|---|---|---|
| H1 | No silent data loss on incompatible independent edits | planner conflict rules; destination backups; conflict reports | `test_conflict_preserves_both_versions`, `test_conflict_never_erases_versions`, stale-plan test | VERIFIED locally |
| H2 | Plan before destructive mutation | `Plan`, `SyncPair.plan`, journal embeds plan before apply | planner tests; journal/recovery tests | VERIFIED locally |
| H3 | Deterministic planning | sorted scan/planner; deterministic IDs/hashes | deterministic planner test; repeated-plan property campaign | VERIFIED locally |
| H4 | Baseline only represents last successful commit | `StateStore.write_baseline`; apply/recovery sequencing | disk-full test; crash campaign | VERIFIED locally |
| H5 | Atomic logical commit after operations + verify + durable baseline | engine commit sequence | 15 crash boundaries + recovery | VERIFIED locally |
| H6 | Detect/recover incomplete run without treating partial output as committed | versioned journal; `recover` | crash campaign + repeated recovery | VERIFIED locally |
| H7 | Delete only with baseline evidence and unchanged peer | planner delete table | `test_delete_requires_baseline_evidence`, integration delete test | VERIFIED locally |
| H8 | Preserve recoverable conflict versions | conflict refusal/report, no user mutation on conflict | conflict tests | VERIFIED locally |
| H9 | Root confinement / traversal defense | `validate_relpath`, `confined_path`, no-follow traversal | path traversal + symlink-parent tests | VERIFIED locally |
| H10 | Versioned persistent metadata/journal, fail closed | state/journal v1 + checksums | corrupt/truncated state tests | VERIFIED locally |
| H11 | Recovery idempotence | journal outcome inspection + committed-run finalization | repeated recovery test | VERIFIED locally |
| H12 | Post-success logical equivalence | post-apply scan + `_snapshots_equivalent` | integration/property/crash tests | VERIFIED locally |
| R01 | Initial sync overlapping/distinct trees | planner initial rules | initial planner + integration tests | VERIFIED locally |
| R02 | Incremental classification | `classify` | exhaustive one-path reference oracle | VERIFIED locally |
| R03 | SHA-256 content identity | scanner/util | sync + large/zero-byte tests | VERIFIED locally |
| R04 | Exact-content rename detection | planner unique rename matcher | exact rename, rename/modify tests; benchmark rename plan | VERIFIED locally |
| R05 | Required conflict classes | planner | modify/modify, delete/modify, rename/modify, type, initial, case tests | VERIFIED locally: named classes covered by planner/integration tests |
| R06 | Stable conflict identifiers | deterministic SHA-256-derived IDs | deterministic plan tests | VERIFIED locally |
| R07 | Safe conflict materialization/reporting | `.ferrosync/conflicts` checksummed report | conflict integration tests | VERIFIED locally |
| R08 | Dry-run plan + JSON + plan hash | CLI/model | local API tests; installed CLI packaging smoke | VERIFIED locally |
| R09 | Apply lifecycle: lock→validate→scan→plan→journal→apply→verify→baseline→finalize | engine/state | integration/crash tests | VERIFIED locally |
| R10 | Read-only verify | `verify` | integration + artifact-detection tests | VERIFIED locally |
| R11 | Status details | `status` | implementation inspection; exercised indirectly | VERIFIED locally: dedicated status assertion |
| R12 | Safe regular-file replacement | sibling temp, fsync, SHA recheck, atomic install, backup | crash + disk-full + large-file tests | VERIFIED locally |
| R13 | Durable corruption-detectable journal | checked JSON journal | truncated journal + crash tests | VERIFIED locally |
| R14 | Recovery classification/resume/finalize | `recover` | 15-boundary campaign | VERIFIED locally |
| R15 | Symlink default: copy, never traverse, confine mutations | scanner/engine/util | symlink copy, loop, parent escape | VERIFIED locally on POSIX; Windows symlink lane may skip due host policy |
| R16 | Empty dirs / Unicode / zero-byte / large files | scanner/planner/engine | adversarial integration tests | VERIFIED locally |
| R17 | Case collision handling | portable NFC+casefold policy | casefold collision test | VERIFIED locally |
| R18 | Ignore rules and self-state exclusion | scanner defaults + persisted config | ignored-path baseline test | VERIFIED locally |
| R19 | Change-during-sync / stale plan defense | fresh stat, copy hash, precondition revalidation, post-verify | disappearing-source + stale-destination + final-window source/destination race tests | VERIFIED for declared trust boundary; arbitrary hostile concurrent writer outside contract |
| R20 | Independent reference/property model | one-path oracle + randomized real-FS sequences | 27 transition combinations; 40 seeds × 12 rounds | VERIFIED locally |
| R21 | Performance/scale harness | `bench.py`, `scale_plan.py` | committed local JSON results; 1,000,000-path planner run | VERIFIED observationally |
| R22 | CLI minimum commands | `cli.py` | source + installed CLI smoke | VERIFIED locally |
| R23 | Library API | `SyncPair.open/plan/apply` | integration + stale-plan API tests | VERIFIED locally |
| R24 | Linux/macOS/Windows target | CI matrix | workflow defined | UNVERIFIED until CI completes on all lanes |
| R25 | Packaging / clean install | `pyproject.toml` | offline wheel + clean venv installed CLI smoke | VERIFIED locally |
| R26 | Required documentation | README + 12 docs | repository inspection | VERIFIED |
| R27 | CI real gates | `.github/workflows/ci.yml` | workflow defined | UNVERIFIED until GitHub run completes |
| R28 | Evidence system / real manifest | `evidence/*`, `verify_manifest.py` | positive verification + negative tamper test | VERIFIED locally |
| R29 | No external sync engine | repository implementation | dependency/source inspection | VERIFIED |
| R30 | State parsing bounded, no executable serialization | 16 MiB bound + JSON only | implementation + corrupt-state tests | VERIFIED locally |

## Declared crash injection labels

`after_journal_creation`, `before_source_read`, `during_copy`, `after_temp_write`, `after_file_fsync`, `before_rename`, `after_rename`, `before_directory_fsync`, `after_operation`, `before_verification`, `after_verification`, `before_baseline_write`, `during_baseline_write`, `after_baseline_replace`, `before_journal_finalize`.

All 15 are exercised by `tests/test_crash_recovery.py` on the local Linux campaign environment.
