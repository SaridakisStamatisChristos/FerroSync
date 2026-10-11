# Limitations

- No automatic text/content merge; incompatible concurrent edits are conflicts.
- Directory renames are not inferred as one atomic rename; exact file/symlink renames are supported.
- Conflict resolution is external in 0.1; FerroSync records conflicts but does not choose a winner.
- Directory permissions, ownership, ACLs, xattrs, and timestamp fidelity are not synchronized as contractual metadata.
- Windows directory fsync is not claimed.
- Safe regular-file commit requires same-filesystem hard-link support in the destination directory; FerroSync fails closed rather than falling back to an overwrite-prone install when that primitive is unavailable.
- Portable case/Unicode namespace policy is conservative and may reject names valid on a specific Linux filesystem.
- Arbitrary hostile concurrent writers are outside the security contract; see `SECURITY.md`.
- State is anchored under LEFT, so root order must remain stable.
- No network/distributed synchronization transport is included; both roots must be accessible to the local process.
- No public redistribution license is granted by this repository as created; the owner must choose licensing before public distribution.
