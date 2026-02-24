"""Scan-related models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid

from .common import DateRange, RecoveredFile


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanConfig(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["trash", "apfs_snapshot", "time_machine"])
    date_range: Optional[DateRange] = None
    file_types: list[str] = Field(default_factory=list)  # e.g. ["image", "document"]
    file_extensions: list[str] = Field(default_factory=list)  # e.g. [".jpg", ".pdf"]
    volume: str = "/"


class ScanProgress(BaseModel):
    current_source: str = ""
    files_found: int = 0
    sources_completed: int = 0
    sources_total: int = 0
    message: str = ""
    percent: float = 0.0


class ScanJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    config: ScanConfig
    status: ScanStatus = ScanStatus.PENDING
    progress: ScanProgress = Field(default_factory=ScanProgress)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ScanResult(BaseModel):
    job_id: str
    files: list[RecoveredFile] = Field(default_factory=list)
    total_files: int = 0
    total_size: int = 0
