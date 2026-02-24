"""Wrappers for macOS system commands."""

import asyncio
import platform
from typing import Optional


async def run_cmd(
    *args: str,
    sudo: bool = False,
    timeout: float = 30.0,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr).

    When sudo=True, uses sudo -S and pipes the stored password via stdin.
    Falls back to sudo -n (cached creds) if no password is stored.
    """
    cmd = list(args)
    stdin_data = None

    if sudo:
        # Import here to avoid circular imports
        from ..scanners.file_carving import get_sudo_password
        password = get_sudo_password()
        if password:
            cmd = ["sudo", "-S"] + cmd
            stdin_data = f"{password}\n".encode()
        else:
            cmd = ["sudo", "-n"] + cmd

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_data), timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "Command timed out"

    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )


async def get_hostname() -> str:
    rc, out, _ = await run_cmd("hostname")
    return out if rc == 0 else "unknown"


async def get_os_version() -> str:
    return f"macOS {platform.mac_ver()[0]}"


async def list_local_snapshots(volume: str = "/") -> list[str]:
    """List APFS local snapshots via tmutil, falling back to diskutil."""
    snapshots = []

    # Try tmutil first (works without sudo)
    rc, out, _ = await run_cmd("tmutil", "listlocalsnapshots", volume)
    if rc == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("com.apple."):
                snapshots.append(line)
            elif "." in line and not line.startswith("Snapshots"):
                snapshots.append(line)

    if snapshots:
        return snapshots

    # Try tmutil with sudo
    rc, out, _ = await run_cmd("tmutil", "listlocalsnapshots", volume, sudo=True)
    if rc == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("com.apple."):
                snapshots.append(line)
            elif "." in line and not line.startswith("Snapshots"):
                snapshots.append(line)

    if snapshots:
        return snapshots

    # Fallback: try diskutil apfs listsnapshots on the data volume
    rc, out, _ = await run_cmd("diskutil", "apfs", "listSnapshots", "/")
    if rc == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if "com.apple." in line:
                # Extract snapshot name from diskutil output
                if "Name:" in line:
                    name = line.split("Name:")[-1].strip()
                    snapshots.append(name)
                elif line.startswith("com.apple."):
                    snapshots.append(line)

    return snapshots


async def mount_snapshot(
    snapshot_name: str,
    volume: str,
    mount_point: str,
) -> tuple[bool, str]:
    """Mount an APFS snapshot read-only. Returns (success, message)."""
    rc, out, err = await run_cmd(
        "mount_apfs", "-o", "rdonly", "-s", snapshot_name, volume, mount_point,
        sudo=True,
        timeout=60.0,
    )
    if rc == 0:
        return True, f"Mounted {snapshot_name} at {mount_point}"
    return False, err or out


async def unmount_snapshot(mount_point: str) -> tuple[bool, str]:
    """Unmount a snapshot mount point."""
    rc, out, err = await run_cmd("umount", mount_point, sudo=True, timeout=30.0)
    if rc == 0:
        return True, "Unmounted"
    return False, err or out


async def list_diskutil_volumes() -> list[dict]:
    """List volumes via diskutil."""
    rc, out, _ = await run_cmd("diskutil", "list", "-plist")
    # Simplified: just use df for volume info
    rc, out, _ = await run_cmd("df", "-h")
    if rc != 0:
        return []
    volumes = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6:
            mount = parts[-1]
            volumes.append({
                "device": parts[0],
                "mount_point": mount,
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
            })
    return volumes


async def get_tm_destination() -> Optional[str]:
    """Get Time Machine backup destination path."""
    rc, out, _ = await run_cmd("tmutil", "destinationinfo")
    if rc != 0:
        return None
    for line in out.splitlines():
        if "Mount Point" in line:
            return line.split(":", 1)[-1].strip()
    return None


async def list_tm_backups() -> list[str]:
    """List Time Machine backup paths."""
    rc, out, _ = await run_cmd("tmutil", "listbackups")
    if rc != 0 or not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


async def get_xattr(path: str, attr: str) -> Optional[str]:
    """Read an extended attribute from a file."""
    rc, out, _ = await run_cmd("xattr", "-p", attr, path)
    if rc == 0:
        return out
    return None


async def mdls_dates(path: str) -> dict[str, str]:
    """Get Spotlight metadata dates for a file."""
    rc, out, _ = await run_cmd(
        "mdls", "-name", "kMDItemContentCreationDate",
        "-name", "kMDItemContentModificationDate",
        "-name", "kMDItemFSCreationDate",
        path,
    )
    dates = {}
    if rc == 0:
        for line in out.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                val = val.strip().strip('"')
                if val and val != "(null)":
                    dates[key.strip()] = val
    return dates
