# Recovery

`ferrosync recover LEFT RIGHT` handles exactly one incomplete journal. Multiple incomplete journals fail closed for manual inspection.

Recovery first validates pair identity, journal checksum/version, embedded plan identity, operation identity uniqueness, and journal/plan equivalence. It refuses to break a lock owned by a different live PID. A same-run stale lock is removed before recovery.

For each operation, recovery determines whether the intended final state is already present. Otherwise it reuses the original preconditions and resumes only when they remain valid. A destination backup from a partially applied replacement must match the planned prior state.

After all operations, recovery rescans both trees. The baseline advances only if logical equivalence holds. If the baseline already records the interrupted run (crash after baseline replacement), recovery verifies the trees and only finalizes the journal/cleanup.

Recovery is idempotent: once finalized, another `recover` returns `CLEAN` and does not replay destructive work.
