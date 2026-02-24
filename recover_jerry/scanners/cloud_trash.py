"""Cloud trash scanner (Phase 2 stub)."""

from typing import AsyncIterator, Callable, Optional

from ..models.common import RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from .base import BaseScanner
from .registry import register_scanner


class CloudTrashScanner(BaseScanner):
    source_id = "cloud_trash"
    name = "Cloud Trash"
    description = "Check cloud storage trash (Phase 2)"

    async def check_availability(self) -> SourceAvailability:
        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=False,
            detail="Coming in Phase 2 — iCloud, Google Drive, Dropbox trash",
        )

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        return
        yield

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        return None


register_scanner(CloudTrashScanner())
