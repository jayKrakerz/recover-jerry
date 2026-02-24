"""Core shared models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class DateRange(BaseModel):
    start: datetime
    end: datetime


class FileMetadata(BaseModel):
    size: int = 0
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    accessed: Optional[datetime] = None
    deleted_date: Optional[datetime] = None
    mime_type: Optional[str] = None


class RecoveredFile(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_id: str
    original_path: str
    filename: str
    extension: str = ""
    metadata: FileMetadata = Field(default_factory=FileMetadata)
    access_path: str = ""  # internal: where to actually read the file
