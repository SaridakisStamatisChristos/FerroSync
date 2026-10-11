# Claims ledger

| Claim | State | Evidence / calibration |
|---|---|---|
| Bidirectional synchronization does not designate one user-data side as globally authoritative. | VERIFIED | two-sided incremental integration + property campaign; CI matrix green |
| Incompatible concurrent edits are not silently overwritten. | VERIFIED | conflict preservation tests; CI matrix green |
| Delete propagation is baseline-gated. | VERIFIED | planner + integration tests; CI matrix green |
| Planning is deterministic for identical logical inputs. | VERIFIED | deterministic test + repeated seeded plans; CI matrix green |
| Recovery is safe/idempotent at the 15 declared injected boundaries. | VERIFIED | crash campaign; CI matrix green |
| Corrupt/truncated v1 baseline/journal fails closed. | VERIFIED | state/journal adversarial tests; CI matrix green |
| Symlinks are not followed during traversal. | VERIFIED on POSIX; Windows privilege-dependent | POSIX symlink tests execute; Windows symlink tests are skipped where runner privilege/developer mode does not permit creation |
| Installed wheel/CLI works. | VERIFIED | local clean-venv smoke plus GitHub Actions run `38156641062` installed-package smoke on all six matrix lanes |
| Million-path synthetic no-op plan completes. | OBSERVED | `scale_local.json`: 1,000,000 paths, 0 ops/conflicts |
| Linux/macOS/Windows support across Python 3.10/3.13 is verified for the declared CI matrix. | VERIFIED | GitHub Actions run `38156641062`: all six jobs passed compile/static, test, manifest, wheel-build, and installed-CLI-smoke gates |
| FerroSync is faster than another sync engine. | NOT CLAIMED | no comparative benchmark |
| Identical durability semantics hold on every filesystem/OS. | NOT CLAIMED | directory fsync/platform semantics differ |
| Production-ready for arbitrary hostile concurrent writers. | NOT CLAIMED | explicitly outside trust model |
| Cryptographic authenticity of state against malicious rewrite. | NOT CLAIMED | checksum is corruption detection, not keyed authentication |
