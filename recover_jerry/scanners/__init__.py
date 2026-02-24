"""File scanners."""

from .registry import scanner_registry, get_scanner, get_all_scanners
from .trash import TrashScanner
from .apfs_snapshot import APFSSnapshotScanner
from .time_machine import TimeMachineScanner
from .spotlight import SpotlightScanner
from .file_carving import FileCarvingScanner
from .cloud_trash import CloudTrashScanner

__all__ = [
    "scanner_registry",
    "get_scanner",
    "get_all_scanners",
    "TrashScanner",
    "APFSSnapshotScanner",
    "TimeMachineScanner",
    "SpotlightScanner",
    "FileCarvingScanner",
    "CloudTrashScanner",
]
