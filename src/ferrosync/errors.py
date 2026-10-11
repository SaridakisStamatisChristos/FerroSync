class FerroSyncError(Exception):
    """Base error for FerroSync."""


class StateError(FerroSyncError):
    """Persistent state is malformed, unsupported, or inconsistent."""


class PathSafetyError(FerroSyncError):
    """A path failed root-confinement or symlink-parent checks."""


class ConflictError(FerroSyncError):
    """A plan contains conflicts and cannot be applied automatically."""


class StalePlanError(FerroSyncError):
    """Filesystem state no longer matches a plan precondition."""


class RecoveryRequired(FerroSyncError):
    """An interrupted run requires explicit recovery or manual intervention."""


class LockError(FerroSyncError):
    """The synchronization pair is already locked."""


class InjectedCrash(BaseException):
    """Deterministic test-only fault injection that models abrupt interruption."""
