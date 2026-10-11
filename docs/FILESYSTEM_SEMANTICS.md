# Filesystem semantics

## Objects

Regular files, directories, empty directories, and symlinks are supported. Other special objects (devices, sockets, FIFOs) fail closed.

Symlinks are copied as symlinks and never followed during traversal. A symlink in any parent component of a mutation path is rejected. Relative, absolute, dangling, loop, and directory-target symlinks are therefore treated as link objects, not traversal instructions.

## Metadata

Content correctness dominates metadata fidelity. Regular-file POSIX mode bits are copied when available. Directory modes, ownership, ACLs, xattrs, creation times, and exact timestamp fidelity are **not** promised in 0.1. Windows mode semantics are not treated as POSIX permissions.

## Names

Unicode names are supported as supplied by Python/the host OS. FerroSync's portable namespace rejects distinct NFC+casefold-equivalent names. Platform filename restrictions still apply.

## Durability

Regular-file replacement uses same-directory materialization, flush/fsync, content verification, destination capture, then same-filesystem hard-link creation as an atomic no-clobber install before the temp name is removed; directory fsync is used where supported. Windows directory fsync is not claimed. State writes use temp+fsync+replace and directory fsync where available.
