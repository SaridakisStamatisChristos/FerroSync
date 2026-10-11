# Conflicts

Automatic synchronization stops before user-tree mutation when the plan contains a conflict. The original LEFT and RIGHT objects remain where they are. `sync` writes a checksummed report to `LEFT/.ferrosync/conflicts/<plan-id>.json`.

Conflict IDs are deterministic hashes of the conflict kind, logical path, baseline entry, both current entries, and detail string.

Detected classes include initial collisions, modify/modify, modify/delete, delete/modify, add/add, type changes, exact-rename/modify, divergent rename/rename, rename target collision, symlink target divergence (as content divergence), and portable namespace/case collisions.

FerroSync 0.1 does not auto-merge file contents and does not provide an in-place conflict resolver. Resolution is deliberately explicit: preserve/copy the desired versions externally, then rerun `plan`/`sync`.
