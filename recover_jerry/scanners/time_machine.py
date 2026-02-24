"""Time Machine backup scanner."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from ..utils.macos_commands import get_tm_destination, list_tm_backups
from .base import BaseScanner
from .registry import register_scanner


class TimeMachineScanner(BaseScanner):
    source_id = "time_machine"
    name = "Time Machine"
    description = "Scan Time Machine backups for deleted files"

    @property
    def requires_sudo(self) -> bool:
        return True

    async def check_availability(self) -> SourceAvailability:
        dest = await get_tm_destination()
        backups = await list_tm_backups() if dest else []
        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=dest is not None and len(backups) > 0,
            requires_sudo=True,
            detail=f"{len(backups)} backups at {dest}" if dest else "No Time Machine destination found",
            count=len(backups),
        )

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        backups = await list_tm_backups()
        if not backups:
            return

        # Pre-filter by date range
        if config.date_range:
            backups = [
                b for b in backups
                if self._backup_in_range(b, config.date_range)
            ]

        if not backups:
            return

        live_volume = config.volume or "/"

        for backup_path in backups:
            if progress_callback:
                progress_callback(f"Scanning backup {Path(backup_path).name}")

            for rf in self._scan_backup(backup_path, live_volume):
                yield rf

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        try:
            p = Path(file.access_path)
            if p.exists() and p.is_file():
                return p.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    def _backup_in_range(self, backup_path: str, date_range) -> bool:
        """Check if a backup date falls within the target range."""
        backup_date = self._parse_backup_date(backup_path)
        if backup_date is None:
            return True
        start = date_range.start.replace(tzinfo=None) if date_range.start.tzinfo else date_range.start
        end = date_range.end.replace(tzinfo=None) if date_range.end.tzinfo else date_range.end
        bd_naive = backup_date.replace(tzinfo=None) if backup_date.tzinfo else backup_date
        return start <= bd_naive <= end

    def _parse_backup_date(self, backup_path: str) -> Optional[datetime]:
        """Extract date from backup path like .../2025-12-15-123456"""
        match = re.search(r"(\d{4}-\d{2}-\d{2})-(\d{6})", backup_path)
        if match:
            try:
                return datetime.strptime(
                    f"{match.group(1)} {match.group(2)[:2]}:{match.group(2)[2:4]}:{match.group(2)[4:6]}",
                    "%Y-%m-%d %H:%M:%S",
                )
            except ValueError:
                pass
        return None

    def _scan_backup(self, backup_path: str, live_volume: str) -> list[RecoveredFile]:
        """Walk a TM backup and find files not present on live FS."""
        files = []
        bp = Path(backup_path)

        # TM backups contain a volume directory structure
        # e.g., /Volumes/TMBackup/Backups.backupdb/Mac/2025-12-15-123456/Macintosh HD - Data/
        # Find the volume root inside the backup
        volume_roots = []
        if bp.exists() and bp.is_dir():
            for child in bp.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    volume_roots.append(child)

        if not volume_roots:
            # The backup itself might be the root
            volume_roots = [bp]

        for vol_root in volume_roots:
            scan_dirs = ["Users", "Applications", "Library"]
            for scan_dir in scan_dirs:
                target = vol_root / scan_dir
                if not target.exists():
                    continue

                for root, _dirs, filenames in os.walk(target):
                    for fname in filenames:
                        if fname.startswith("."):
                            continue
                        backup_file = Path(root) / fname
                        relative = backup_file.relative_to(vol_root)
                        live_path = Path(live_volume) / relative

                        if not live_path.exists():
                            rf = self._make_recovered_file(backup_file, str(live_path))
                            if rf:
                                files.append(rf)
        return files

    def _make_recovered_file(
        self,
        path: Path,
        original_path: str,
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
register_scanner(TimeMachineScanner())
