"""APFS local snapshot scanner."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from ..config import settings
from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from ..utils.macos_commands import (
    list_local_snapshots,
    mount_snapshot,
    unmount_snapshot,
)
from .base import BaseScanner
from .registry import register_scanner


class APFSSnapshotScanner(BaseScanner):
    source_id = "apfs_snapshot"
    name = "APFS Snapshots"
    description = "Scan APFS local snapshots for deleted files"

    def __init__(self):
        self._mounted: list[str] = []  # track mounted paths for cleanup

    @property
    def requires_sudo(self) -> bool:
        return True

    async def check_availability(self) -> SourceAvailability:
        snapshots = await list_local_snapshots("/")
        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=len(snapshots) > 0,
            requires_sudo=True,
            detail=f"{len(snapshots)} local snapshots found",
            count=len(snapshots),
        )

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        volume = config.volume or "/"
        snapshots = await list_local_snapshots(volume)

        # Pre-filter snapshots by date range
        if config.date_range:
            snapshots = [
                s for s in snapshots
                if self._snapshot_in_range(s, config.date_range)
            ]

        if not snapshots:
            return

        mount_base = settings.snapshot_mount_base
        mount_base.mkdir(parents=True, exist_ok=True)

        for snapshot in snapshots:
            snapshot_safe = snapshot.replace("/", "_").replace(" ", "_")
            mount_point = str(mount_base / snapshot_safe)
            os.makedirs(mount_point, exist_ok=True)

            if progress_callback:
                progress_callback(f"Mounting snapshot {snapshot}")

            success, msg = await mount_snapshot(snapshot, volume, mount_point)
            if not success:
                if progress_callback:
                    progress_callback(f"Failed to mount {snapshot}: {msg}")
                continue

            self._mounted.append(mount_point)

            try:
                if progress_callback:
                    progress_callback(f"Scanning snapshot {snapshot}")

                for rf in self._scan_snapshot(mount_point, volume, snapshot):
                    yield rf
            finally:
                await unmount_snapshot(mount_point)
                self._mounted.remove(mount_point)

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        try:
            p = Path(file.access_path)
            if p.exists() and p.is_file():
                return p.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    async def cleanup(self):
        """Unmount all mounted snapshots."""
        for mp in list(self._mounted):
            await unmount_snapshot(mp)
        self._mounted.clear()

    def _snapshot_in_range(self, snapshot_name: str, date_range) -> bool:
        """Check if a snapshot date falls within the target range."""
        snap_date = self._parse_snapshot_date(snapshot_name)
        if snap_date is None:
            return True  # include if we can't parse the date
        start = date_range.start.replace(tzinfo=None) if date_range.start.tzinfo else date_range.start
        end = date_range.end.replace(tzinfo=None) if date_range.end.tzinfo else date_range.end
        snap_naive = snap_date.replace(tzinfo=None) if snap_date.tzinfo else snap_date
        return start <= snap_naive <= end

    def _parse_snapshot_date(self, snapshot_name: str) -> Optional[datetime]:
        """Extract date from snapshot name like com.apple.TimeMachine.2025-12-15-123456.local"""
        match = re.search(r"(\d{4}-\d{2}-\d{2})-(\d{6})", snapshot_name)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                return datetime.strptime(
                    f"{date_str} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}",
                    "%Y-%m-%d %H:%M:%S",
                )
            except ValueError:
                pass
        # Try simpler pattern
        match = re.search(r"(\d{4}-\d{2}-\d{2})", snapshot_name)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            except ValueError:
                pass
        return None

    def _scan_snapshot(
        self,
        mount_point: str,
        live_volume: str,
        snapshot_name: str,
    ) -> list[RecoveredFile]:
        """Walk snapshot and find files that don't exist on the live volume."""
        files = []
        mount_path = Path(mount_point)

        # Walk common user directories
        scan_dirs = ["Users", "Applications", "Library"]
        for scan_dir in scan_dirs:
            snapshot_dir = mount_path / scan_dir
            if not snapshot_dir.exists():
                continue

            for root, _dirs, filenames in os.walk(snapshot_dir):
                for fname in filenames:
                    if fname.startswith("."):
                        continue
                    snap_file = Path(root) / fname
                    # Compute the corresponding live path
                    relative = snap_file.relative_to(mount_path)
                    live_path = Path(live_volume) / relative

                    # Only report files that are missing from live FS
                    if not live_path.exists():
                        rf = self._make_recovered_file(snap_file, str(live_path), snapshot_name)
                        if rf:
                            files.append(rf)
        return files

    def _make_recovered_file(
        self,
        path: Path,
        original_path: str,
        snapshot_name: str,
    ) -> Optional[RecoveredFile]:
        try:
            stat = path.stat()
        except (OSError, PermissionError):
            return None

        created = None
        modified = None
        try:
            created = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
        except AttributeError:
            pass
        try:
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        except (OSError, ValueError):
            pass

        ext = path.suffix.lower() if path.suffix else ""

        return RecoveredFile(
            source_id=self.source_id,
            original_path=original_path,
            filename=path.name,
            extension=ext,
            metadata=FileMetadata(
                size=stat.st_size,
                created=created,
                modified=modified,
            ),
            access_path=str(path),
        )


# Auto-register
register_scanner(APFSSnapshotScanner())
