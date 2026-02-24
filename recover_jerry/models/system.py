"""System information models."""

from typing import Optional
from pydantic import BaseModel, Field


class VolumeInfo(BaseModel):
    name: str
    mount_point: str
    filesystem: str = ""
    total_size: int = 0
    free_space: int = 0
    is_boot: bool = False


class SourceAvailability(BaseModel):
    source_id: str
    name: str
    available: bool = False
    requires_sudo: bool = False
    has_sudo: bool = False
    detail: str = ""
    count: Optional[int] = None  # e.g. number of snapshots, backups


class SystemInfo(BaseModel):
    hostname: str = ""
    os_version: str = ""
    volumes: list[VolumeInfo] = Field(default_factory=list)
    sources: list[SourceAvailability] = Field(default_factory=list)
    has_full_disk_access: bool = False
    sudo_cached: bool = False
