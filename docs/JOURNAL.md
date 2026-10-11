# Journal

Journal format version: **1**.

A run persists its full plan before user-tree mutation. Run state progresses through `PLANNED -> STARTED -> VERIFIED -> COMMITTED`; each operation progresses through the applicable subset of `PLANNED`, `STARTED`, `MATERIALIZED`, `RENAMED`, and `VERIFIED`.

Operation records include deterministic IDs, action, side, relative path, source path/side, expected source state, expected destination-before state, expected destination-after state, and destructive classification.

For replacement and deletion, deterministic sibling backup names preserve the prior destination until logical commit. Regular-file writes are materialized in a sibling temp file, flushed/fsynced, verified against the planned hash, then atomically installed. Backups and temps are cleanup artifacts, never baseline authority.

Recovery validates that the journal operation list exactly matches the embedded plan and rejects duplicate or forged operation IDs. A journal checksum detects accidental truncation/corruption; it is not a cryptographic authenticity mechanism against an attacker who can rewrite both state and checksum.
