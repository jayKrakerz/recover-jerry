"""Abstract base scanner interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Optional

from ..models.common import RecoveredFile
from ..models.scan import ScanConfig, ScanProgress
from ..models.system import SourceAvailability


class BaseScanner(ABC):
    """All scanners implement this interface."""

    source_id: str = ""
    name: str = ""
    description: str = ""

    @property
    def requires_sudo(self) -> bool:
        return False

    @abstractmethod
    async def check_availability(self) -> SourceAvailability:
        """Check whether this scanner source is usable on this system."""
        ...

    @abstractmethod
    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        """Scan and yield recovered files matching the config."""
        ...

    @abstractmethod
    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        """Read file content for preview or recovery."""
        ...
