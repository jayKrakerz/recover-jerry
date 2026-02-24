"""File carving scanner via PhotoRec (non-interactive /cmd mode)."""

import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from .base import BaseScanner
from .registry import register_scanner

logger = logging.getLogger(__name__)

# Singleton to hold sudo password for the session
_sudo_password: Optional[str] = None


def set_sudo_password(password: str):
    global _sudo_password
    _sudo_password = password


def get_sudo_password() -> Optional[str]:
    return _sudo_password


def _find_photorec() -> Optional[str]:
    return shutil.which("photorec")


def _get_data_volume_device() -> Optional[str]:
    """Find the physical disk device for the APFS container holding user data.

    On macOS, synthesized APFS volumes (disk3s1 etc.) are 'Resource busy'
    when mounted. PhotoRec needs the physical store device (disk0s2).
    """
    import subprocess

    # Strategy 1: Find the APFS physical store for the data volume
    try:
        result = subprocess.run(
            ["diskutil", "apfs", "list", "-plist"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            import plistlib
            plist = plistlib.loads(result.stdout.encode())
            for container in plist.get("Containers", []):
                # Check if this container has the Data volume
                for vol in container.get("Volumes", []):
                    roles = vol.get("Roles", [])
                    if "Data" in roles or vol.get("Name", "").endswith("- Data"):
                        # Found it — return the physical store device
                        stores = container.get("PhysicalStores", [])
                        if stores:
                            dev_id = stores[0].get("DeviceIdentifier", "")
                            if dev_id:
                                return f"/dev/{dev_id}"
    except Exception:
        pass

    # Strategy 2: Parse diskutil list for the physical disk
    try:
        result = subprocess.run(
            ["diskutil", "list"], capture_output=True, text=True, timeout=10,
        )
        # Look for the physical disk that contains the APFS container
        lines = result.stdout.splitlines()
        physical_disk = None
        for line in lines:
            if "internal, physical" in line:
                # e.g. /dev/disk0 (internal, physical):
                physical_disk = line.split()[0]
            if physical_disk and "Apple_APFS" in line and "Container" in line:
                parts = line.split()
                if parts:
                    dev = parts[-1]  # e.g. disk0s2
                    return f"/dev/{dev}"
    except Exception:
        pass

    return None


async def _test_sudo(password: str) -> bool:
    """Test if a password works for sudo."""
    proc = await asyncio.create_subprocess_exec(
        "sudo", "-S", "-v",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    proc.stdin.write(f"{password}\n".encode())
    await proc.stdin.drain()
    proc.stdin.close()
    await proc.wait()
    return proc.returncode == 0


class FileCarvingScanner(BaseScanner):
    source_id = "file_carving"
    name = "File Carving (PhotoRec)"
    description = "Deep scan raw disk for permanently deleted files"

    def __init__(self):
        self._output_base: Optional[str] = None
        self._output_dir: Optional[str] = None
        self._process: Optional[asyncio.subprocess.Process] = None

    @property
    def requires_sudo(self) -> bool:
        return True

    async def check_availability(self) -> SourceAvailability:
        photorec = _find_photorec()
        device = _get_data_volume_device()
        has_password = _sudo_password is not None

        if not photorec:
            return SourceAvailability(
                source_id=self.source_id,
                name=self.name,
                available=False,
                requires_sudo=True,
                detail="PhotoRec not found. Install: brew install testdisk",
            )

        parts = ["PhotoRec ready"]
        if device:
            parts.append(f"device {device}")
        if not has_password:
            parts.append("enter sudo password to enable")
        else:
            parts.append("sudo authenticated")

        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=photorec is not None,
            requires_sudo=True,
            has_sudo=has_password,
            detail=" — ".join(parts),
        )

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        photorec = _find_photorec()
        if not photorec:
            logger.warning("PhotoRec not installed — skipping file carving")
            if progress_callback:
                progress_callback("PhotoRec not installed")
            return

        password = get_sudo_password()
        if not password:
            logger.warning("Sudo password not set — skipping file carving")
            if progress_callback:
                progress_callback("Sudo password not provided — enter it on the Dashboard first")
            return

        device = _get_data_volume_device()
        if not device:
            logger.warning("Could not determine disk device — skipping file carving")
            if progress_callback:
                progress_callback("Could not determine disk device")
            return

        # Create output base path.
        # PhotoRec /d <path> creates <path>.1/, <path>.2/ etc. as output dirs.
        # We use a temp directory and set _output_dir to the base path;
        # the actual files will be in <base>.1/
        tmp_base = tempfile.mkdtemp(prefix="recover-jerry-carve-")
        self._output_base = tmp_base  # PhotoRec will create <tmp_base>.1/
        self._output_dir = f"{tmp_base}.1"  # Where files actually end up

        if progress_callback:
            progress_callback(f"Starting PhotoRec on {device}...")

        # Build the /cmd command string
        cmd_parts = []

        # File type options
        if config.file_extensions:
            cmd_parts.append("fileopt")
            cmd_parts.append("everything")
            cmd_parts.append("disable")
            for ext in config.file_extensions:
                ext_clean = ext.lstrip(".").lower()
                cmd_parts.append(ext_clean)
                cmd_parts.append("enable")
        elif config.file_types:
            cmd_parts.append("fileopt")
            cmd_parts.append("everything")
            cmd_parts.append("disable")
            type_exts = {
                "image": ["jpg", "png", "gif", "bmp", "tif", "raw", "cr2", "heic"],
                "document": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "rtf", "txt"],
                "video": ["mov", "mp4", "avi", "mkv"],
                "audio": ["mp3", "wav", "aac", "flac", "m4a", "aif", "ogg"],
                "code": ["py", "js", "html", "json", "xml"],
            }
            for ft in config.file_types:
                for ext in type_exts.get(ft, []):
                    cmd_parts.append(ext)
                    cmd_parts.append("enable")
        else:
            cmd_parts.append("fileopt")
            cmd_parts.append("everything")
            cmd_parts.append("enable")

        # Scan free space only (where deleted files live)
        cmd_parts.append("freespace")

        # Start the scan
        cmd_parts.append("search")

        cmd_string = ",".join(cmd_parts)

        if progress_callback:
            progress_callback(f"PhotoRec scanning {device} (free space)... this may take 30-60+ minutes")

        logger.info(f"PhotoRec command: sudo -S {photorec} /log /d {self._output_base} /cmd {device} {cmd_string}")
        logger.info(f"PhotoRec output will be in: {self._output_dir}")

        try:
            # Run PhotoRec non-interactively via /cmd
            # /d uses the base path — PhotoRec creates <base>.1/ for output
            self._process = await asyncio.create_subprocess_exec(
                "sudo", "-S",
                photorec, "/log", "/d", self._output_base,
                "/cmd", device, cmd_string,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Send password
            self._process.stdin.write(f"{password}\n".encode())
            await self._process.stdin.drain()
            self._process.stdin.close()

            # Monitor progress
            last_count = 0
            while True:
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=10.0)
                    break
                except asyncio.TimeoutError:
                    count = self._count_recovered_files()
                    if count != last_count or count == 0:
                        last_count = count
                        if progress_callback:
                            progress_callback(
                                f"PhotoRec scanning... {count} files recovered so far"
                            )

            # Read any remaining output
            remaining_output = b""
            try:
                remaining_output = await self._process.stdout.read()
            except Exception:
                pass
            logger.info(
                f"PhotoRec exited with code {self._process.returncode}. "
                f"Output tail: {remaining_output[-500:].decode('utf-8', errors='replace')}"
            )

            total = self._count_recovered_files()
            if progress_callback:
                progress_callback(f"PhotoRec finished. {total} files carved. Processing results...")

            # Collect results
            for rf in self._collect_results(config):
                yield rf

        except Exception as e:
            logger.error(f"PhotoRec error: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"PhotoRec error: {e}")

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        try:
            p = Path(file.access_path)
            if p.exists() and p.is_file():
                return p.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    def _get_output_files(self) -> list[Path]:
        """Find all recovered files in PhotoRec output.

        PhotoRec may place files:
        - Directly in the output dir (e.g. <base>.1/)
        - In recup_dir.N subdirectories
        """
        if not self._output_dir:
            return []

        output_path = Path(self._output_dir)
        if not output_path.exists():
            return []

        result = []
        try:
            for entry in output_path.iterdir():
                if entry.is_file() and not entry.name.startswith(".") and entry.name != "report.xml":
                    result.append(entry)
                elif entry.is_dir() and entry.name.startswith("recup_dir"):
                    try:
                        for f in entry.iterdir():
                            if f.is_file() and not f.name.startswith("."):
                                result.append(f)
                    except PermissionError:
                        pass
        except PermissionError:
            pass

        return result

    def _count_recovered_files(self) -> int:
        return len(self._get_output_files())

    def _collect_results(self, config: ScanConfig) -> list[RecoveredFile]:
        files = []
        for fpath in sorted(self._get_output_files()):
            try:
                stat = fpath.stat()
            except OSError:
                continue
            if stat.st_size == 0:
                continue

            ext = fpath.suffix.lower() if fpath.suffix else ""

            created = None
            modified = None
            try:
                created = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
            except AttributeError:
                pass
            try:
                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            except (OSError, ValueError):
                pass

            rf = RecoveredFile(
                source_id=self.source_id,
                original_path=f"[carved] {fpath.name}",
                filename=fpath.name,
                extension=ext,
                metadata=FileMetadata(
                    size=stat.st_size,
                    created=created,
                    modified=modified,
                ),
                access_path=str(fpath),
            )
            files.append(rf)

        return files

    async def cleanup(self):
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._process.kill()


register_scanner(FileCarvingScanner())
