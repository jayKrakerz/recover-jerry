"""Detect volumes, snapshots, Time Machine, and permissions."""

import shutil
from pathlib import Path

from ..models.system import SystemInfo, VolumeInfo
from ..utils.macos_commands import get_hostname, get_os_version, list_diskutil_volumes
from ..utils.permissions import check_sudo_cached, check_full_disk_access
from ..scanners.registry import get_all_scanners


async def inspect_system() -> SystemInfo:
    """Gather full system info for the dashboard."""
    hostname = await get_hostname()
    os_version = await get_os_version()
    sudo_cached = await check_sudo_cached()
    fda = await check_full_disk_access()

    # Get volumes
    raw_volumes = await list_diskutil_volumes()
    volumes = []
    for rv in raw_volumes:
        mp = rv.get("mount_point", "")
        volumes.append(VolumeInfo(
            name=Path(mp).name or mp,
            mount_point=mp,
            is_boot=(mp == "/"),
        ))

    # Check each scanner's availability
    scanners = get_all_scanners()
    sources = []
    for scanner in scanners.values():
        avail = await scanner.check_availability()
        avail.has_sudo = sudo_cached
        sources.append(avail)

    return SystemInfo(
        hostname=hostname,
        os_version=os_version,
        volumes=volumes,
        sources=sources,
        has_full_disk_access=fda,
        sudo_cached=sudo_cached,
    )
