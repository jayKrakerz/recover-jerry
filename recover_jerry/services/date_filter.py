"""Centralized date filtering logic."""

from datetime import datetime
from typing import Optional

from ..models.common import DateRange, FileMetadata, RecoveredFile


def file_matches_date_range(file: RecoveredFile, date_range: Optional[DateRange]) -> bool:
    """Check if a file's dates fall within the target range.

    Waterfall priority: deleted_date > modified > created > accessed
    If no date is available, include the file (conservative).
    """
    if date_range is None:
        return True

    best_date = get_best_date(file.metadata)
    if best_date is None:
        return True  # no date info, include conservatively

    start = _normalize(date_range.start)
    end = _normalize(date_range.end)
    check = _normalize(best_date)

    return start <= check <= end


def get_best_date(metadata: FileMetadata) -> Optional[datetime]:
    """Get the most relevant date from file metadata (waterfall)."""
    for dt in [metadata.deleted_date, metadata.modified, metadata.created, metadata.accessed]:
        if dt is not None:
            return dt
    return None


def _normalize(dt: datetime) -> datetime:
    """Strip timezone for comparison."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt
