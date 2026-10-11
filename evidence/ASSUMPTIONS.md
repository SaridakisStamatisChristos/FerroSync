# Assumption ledger

| ID | Statement | Criticality | Confidence | Affected surfaces | Invalidation trigger |
|---|---|---|---|---|---|
| A01 | Python 3.10+ is acceptable for this local-first systems tool. | MEDIUM | HIGH | packaging, implementation | user requires native binary / older runtime |
| A02 | Zero runtime third-party dependencies are preferred for portability and auditability. | LOW | HIGH | architecture | required feature needs external library |
| A03 | LEFT is metadata anchor only; data authority remains symmetric. Root order is persistent identity. | HIGH | HIGH | state/recovery | requirement demands order-independent state discovery |
| A04 | Conflicts should fail closed rather than auto-merge or choose a winner. | HIGH | HIGH | planner/conflicts | user specifies merge policy |
| A05 | Exact-content file/symlink rename detection satisfies the minimum; ambiguous and directory-level rename inference may conservatively conflict. | MEDIUM | HIGH | planner | enhanced rename semantics required |
| A06 | Portable NFC+casefold uniqueness is a safer default than host-specific permissiveness. | MEDIUM | MEDIUM | namespace behavior | user requires Linux-only exact case-sensitive namespace |
| A07 | POSIX regular-file mode bits are useful metadata; ownership/ACL/xattr/timestamp fidelity is out of the v0.1 contract. | MEDIUM | HIGH | metadata semantics | stronger metadata fidelity requested |
| A08 | A process with arbitrary hostile concurrent write access to both roots is outside the security contract; ordinary change-during-sync is still detected where portable primitives permit. | HIGH | HIGH | security/TOCTOU | hostile-writer sandboxing becomes a hard requirement |
| A09 | No public/open-source license is inferred. The private repository grants no new redistribution rights by this campaign. | HIGH | HIGH | legal/package metadata | owner explicitly selects a license |
| A10 | SHA-256 is the v1 content hash; changing it requires an explicit state-format migration/version policy. | MEDIUM | HIGH | identity/state | hash policy changes |
