"""Sudo helper for privileged operations."""

import asyncio


async def ensure_sudo() -> bool:
    """Check that sudo -n works (credentials cached). Returns True if available."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-n", "true",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return proc.returncode == 0


async def run_privileged(
    *args: str,
    timeout: float = 60.0,
) -> tuple[int, str, str]:
    """Run a command with sudo -n. Returns (returncode, stdout, stderr)."""
    cmd = ["sudo", "-n"] + list(args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "Command timed out"

    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )
