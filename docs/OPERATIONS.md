# Operations guide

## Normal cycle

1. `ferrosync init LEFT RIGHT`
2. `ferrosync plan LEFT RIGHT --json`
3. Inspect conflicts/destructive operations and `plan_id`.
4. `ferrosync sync LEFT RIGHT`
5. `ferrosync verify LEFT RIGHT`

`status` reports baseline ID, last successful commit timestamp, pending operations, conflicts, incomplete run state, tracked paths, current path counts, and data volume.

## Interrupted run

Do not delete `.ferrosync/journal/` or backup/temp artifacts manually. Run `ferrosync recover LEFT RIGHT`. If recovery reports stale assumptions/manual intervention, preserve the trees and journal for diagnosis.

## Pair identity

Always invoke the pair in its initialized LEFT/RIGHT order. Swapping roots intentionally fails persisted root-identity validation.

## Exit codes

- `0`: command succeeded
- `2`: conflict plan / sync conflict
- `3`: verification reported issues
- `4`: FerroSync or filesystem error
- `99`: deterministic injected crash (test harness)
