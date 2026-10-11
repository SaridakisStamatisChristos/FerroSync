# Claims ledger

| Claim | State | Evidence / calibration |
|---|---|---|
| Bidirectional synchronization does not designate one user-data side as globally authoritative. | VERIFIED locally | two-sided incremental integration + property campaign |
| Incompatible concurrent edits are not silently overwritten. | VERIFIED locally | conflict preservation tests |
| Delete propagation is baseline-gated. | VERIFIED locally | planner + integration tests |
| Planning is deterministic for identical logical inputs. | VERIFIED locally | deterministic test + repeated seeded plans |
| Recovery is safe/idempotent at the 15 declared injected boundaries. | VERIFIED locally | crash campaign |
| Corrupt/truncated v1 baseline/journal fails closed. | VERIFIED locally | state/journal adversarial tests |
| Symlinks are not followed during traversal. | VERIFIED locally on POSIX | symlink tests; Windows behavior subject to CI/host privilege |
| Installed wheel/CLI works. | VERIFIED locally | offline wheel build + clean venv smoke |
| Million-path synthetic no-op plan completes. | OBSERVED | `scale_local.json`: 1,000,000 paths, 0 ops/conflicts |
| FerroSync is faster than another sync engine. | NOT CLAIMED | no comparative benchmark |
| Identical durability semantics hold on every filesystem/OS. | NOT CLAIMED | directory fsync/platform semantics differ |
| Linux/macOS/Windows support is fully verified. | UNVERIFIED until CI | matrix exists but repository run must be observed |
| Production-ready for arbitrary hostile concurrent writers. | NOT CLAIMED | explicitly outside trust model |
| Cryptographic authenticity of state against malicious rewrite. | NOT CLAIMED | checksum is corruption detection, not keyed authentication |
