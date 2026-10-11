"""FerroSync public library API."""

from .engine import SyncPair
from .errors import FerroSyncError

__all__ = ["SyncPair", "FerroSyncError"]
__version__ = "0.1.0"
