# Security and trust model

FerroSync treats paths and persisted state as untrusted structured input. Relative paths reject absolute forms, `..`, NUL, drive-like prefixes, and symlink parents. Journal/state parsing is bounded and versioned. Operations derive absolute paths only by joining validated relative paths to already-validated roots.

The scanner never follows symlinks. Regular source opens request `O_NOFOLLOW` where the platform exposes it. Source bytes are hashed while copying and source file identity/mtime/size is rechecked. Destination preconditions are revalidated before mutation, overwritten/deleted destinations are preserved as run backups until commit, and regular-file installation uses an atomic no-clobber hard-link create so a destination that appears in the final commit window is refused rather than overwritten.

Threats explicitly tested include path traversal, symlink-parent escape, symlink loops, corrupt/truncated state, duplicate journal operation IDs, stale plans, permission errors, disk-full behavior, unexpected temp artifacts, and source disappearance during scan.

### Boundary

FerroSync is not an operating-system sandbox. A hostile process with arbitrary concurrent write access to both trees can race filesystem syscalls in ways no portable userspace compare-and-swap primitive can fully exclude. The engine minimizes those windows, preserves captured destinations, and performs post-run equivalence verification; stronger guarantees require cooperative locking or platform-specific primitives.
