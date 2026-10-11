# Synchronization algorithm

## Three-way reasoning

After the first successful run, each logical path is classified independently on each side relative to the committed baseline as `UNCHANGED`, `ADDED`, `MODIFIED`, `DELETED`, `TYPE_CHANGED`, or `METADATA_CHANGED`.

| LEFT | RIGHT | Decision |
|---|---|---|
| unchanged | unchanged | no-op |
| changed | unchanged | propagate LEFT |
| unchanged | changed | propagate RIGHT |
| deleted | unchanged | delete RIGHT, with baseline evidence |
| unchanged | deleted | delete LEFT, with baseline evidence |
| deleted | changed | conflict |
| changed | deleted | conflict |
| changed | changed, same content | no-op |
| changed | changed, different content | conflict |
| type changed | any incompatible state | conflict |

With no baseline, one-sided paths are copied, identical two-sided paths are accepted, and different pre-existing paths at the same name are conflicts. Initial sync never fabricates shared history.

## Content identity

Regular files use SHA-256 over bytes. Symlink identity is SHA-256 over the link target string plus object kind. Directory identity is structural; child paths are represented independently. Size, mode, mtime, and inode are not accepted as substitutes for content identity.

## Rename detection

Exact-content file and symlink renames are detected when a baseline deletion and current addition form a unique identity match on one side. Ambiguous matches are not guessed. Divergent rename/rename and rename/modify cases conflict. Directory rename is intentionally not inferred as one atomic entity; child-level reasoning preserves information and can surface rename/modify conflicts conservatively.

## Portable namespace policy

Before planning, the union of logical paths is normalized with Unicode NFC and `casefold()`. Distinct paths that collapse to the same portable name are conflicts. This intentionally sacrifices some Linux-only namespace freedom to avoid a plan that cannot be represented safely on common Windows/macOS configurations.

## Determinism

Filesystem enumeration is sorted. Plan operations, conflicts, IDs, and the plan hash are derived only from normalized logical inputs. Timestamps are not part of plan identity.
