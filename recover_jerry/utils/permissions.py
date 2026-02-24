"""Permission checking utilities."""

import asyncio
import os
from pathlib import Path


async def check_sudo_cached() -> bool:
    """Check if sudo credentials are cached (non-interactive)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-n", "true",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def check_full_disk_access() -> bool:
    """Heuristic: try reading a FDA-protected path."""
    test_paths = [
        Path.home() / "Library" / "Mail",
        Path.home() / "Library" / "Safari",
    ]
    for p in test_paths:
        try:
            if p.exists():
                list(p.iterdir())
                return True
        except PermissionError:
            return False
    return True  # if test paths don't exist, assume OK


def check_path_writable(path: str) -> bool:
    """Check if a destination path is writable."""
    p = Path(path)
    if p.exists():
        return os.access(str(p), os.W_OK)
    # Check parent
    parent = p.parent
    while not parent.exists():
        parent = parent.parent
    return os.access(str(parent), os.W_OK)
