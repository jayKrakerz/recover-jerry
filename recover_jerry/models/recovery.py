"""Recovery-related models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class RecoveryStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecoveryRequest(BaseModel):
    job_id: str  # scan job to pull files from
    file_ids: list[str]
    destination: str
    preserve_directory_structure: bool = True
    verify_checksums: bool = True


class RecoveryProgress(BaseModel):
    files_recovered: int = 0
    files_total: int = 0
    files_failed: int = 0
    current_file: str = ""
    bytes_copied: int = 0
    bytes_total: int = 0
    percent: float = 0.0
    message: str = ""


class RecoveryFileResult(BaseModel):
    file_id: str
    original_path: str
    recovered_path: str = ""
    success: bool = False
    error: Optional[str] = None
    checksum_match: Optional[bool] = None


class RecoveryJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    request: RecoveryRequest
    status: RecoveryStatus = RecoveryStatus.PENDING
    progress: RecoveryProgress = Field(default_factory=RecoveryProgress)
    results: list[RecoveryFileResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
