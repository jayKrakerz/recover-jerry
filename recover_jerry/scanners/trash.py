"""macOS Trash scanner."""

import os
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from .base import BaseScanner
from .registry import register_scanner


class TrashScanner(BaseScanner):
    source_id = "trash"
    name = "Trash"
    description = "Scan macOS Trash and .Trashes directories"

    @property
    def requires_sudo(self) -> bool:
        return False

    async def check_availability(self) -> SourceAvailability:
        user_trash = Path.home() / ".Trash"
        exists = user_trash.exists()
        count = 0
        detail = ""
        fda_issue = False

        if exists:
            try:
                count = sum(1 for _ in user_trash.iterdir())
                detail = f"{count} items in user Trash"
            except PermissionError:
                fda_issue = True
                # Try osascript as fallback to count items
                count, detail = await self._count_via_osascript()

        if not exists:
            detail = "Trash directory not found"
        elif fda_issue and count == 0:
            detail = "Cannot access Trash — grant Full Disk Access to Terminal, or run: sudo -v"

        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=exists and (count > 0 or not fda_issue),
            requires_sudo=fda_issue,
            detail=detail,
            count=count,
        )

    async def _count_via_osascript(self) -> tuple[int, str]:
        """Use AppleScript to count Trash items when FDA is missing."""
        import asyncio
        try:
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e",
                'tell application "Finder" to return count of items of trash',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            count = int(stdout.decode().strip())
            if count == 0:
                return 0, "Trash is empty"
            return count, f"{count} items in Trash (via Finder)"
        except Exception:
            return 0, "Cannot determine Trash contents"

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        trash_dirs = self._get_trash_dirs()
        found_any = False

        for trash_dir in trash_dirs:
            if not trash_dir.exists():
                continue
            if progress_callback:
                progress_callback(f"Scanning {trash_dir}")

            try:
                items = self._walk_trash(trash_dir)
                for item in items:
                    found_any = True
                    yield item
            except PermissionError:
                if progress_callback:
                    progress_callback(f"Permission denied for {trash_dir}, trying Finder...")

        # If direct access failed, try osascript approach
        if not found_any:
            if progress_callback:
                progress_callback("Trying Finder-based Trash scan...")
            for item in await self._scan_via_osascript():
                yield item

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        try:
            p = Path(file.access_path)
            if p.exists() and p.is_file():
                return p.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    def _get_trash_dirs(self) -> list[Path]:
        dirs = [Path.home() / ".Trash"]
        # Also check volume-level trashes
        uid = os.getuid()
        volumes_dir = Path("/Volumes")
        if volumes_dir.exists():
            for vol in volumes_dir.iterdir():
                trashes = vol / ".Trashes" / str(uid)
                if trashes.exists():
                    dirs.append(trashes)
        return dirs

    def _walk_trash(self, trash_dir: Path) -> list[RecoveredFile]:
        files = []
        try:
            entries = list(trash_dir.iterdir())
        except PermissionError:
            return files

        for entry in entries:
            if entry.name.startswith("."):
                continue

            if entry.is_file():
                rf = self._make_recovered_file(entry)
                if rf:
                    files.append(rf)
            elif entry.is_dir():
                # Recurse into directories in trash
                for root, _dirs, filenames in os.walk(entry):
                    for fname in filenames:
                        if fname.startswith("."):
                            continue
                        fpath = Path(root) / fname
                        rf = self._make_recovered_file(fpath, base_dir=entry)
                        if rf:
                            files.append(rf)
        return files

    def _make_recovered_file(
        self, path: Path, base_dir: Optional[Path] = None,
    ) -> Optional[RecoveredFile]:
        try:
            stat = path.stat()
        except (OSError, PermissionError):
            return None

        original_path = self._get_original_path(path)
        deleted_date = self._get_deletion_date(path)

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

        ext = path.suffix.lower() if path.suffix else ""

        return RecoveredFile(
            source_id=self.source_id,
            original_path=original_path or str(path),
            filename=path.name,
            extension=ext,
            metadata=FileMetadata(
                size=stat.st_size,
                created=created,
                modified=modified,
                deleted_date=deleted_date,
            ),
            access_path=str(path),
        )

    def _get_original_path(self, path: Path) -> Optional[str]:
        """Try reading com.apple.trash.origpath xattr via pure Python."""
        try:
            import xattr as xattr_mod
            val = xattr_mod.getxattr(str(path), "com.apple.trash.origpath")
            return val.decode("utf-8", errors="replace").rstrip("\x00")
        except Exception:
            pass
        # Fallback: try os module
        try:
            val = os.getxattr(str(path), "com.apple.trash.origpath")  # type: ignore[attr-defined]
            return val.decode("utf-8", errors="replace").rstrip("\x00")
        except (AttributeError, OSError):
            pass
        # Last resort: use ctypes to call getxattr
        try:
            return self._getxattr_ctypes(str(path), "com.apple.trash.origpath")
        except Exception:
            pass
        return None

    def _get_deletion_date(self, path: Path) -> Optional[datetime]:
        """Try reading com.apple.trash.deletiondate xattr."""
        raw = None
        try:
            import xattr as xattr_mod
            raw = xattr_mod.getxattr(str(path), "com.apple.trash.deletiondate")
        except Exception:
            pass
        if raw is None:
            try:
                raw = os.getxattr(str(path), "com.apple.trash.deletiondate")  # type: ignore[attr-defined]
            except (AttributeError, OSError):
                pass
        if raw is None:
            try:
                raw = self._getxattr_ctypes_raw(str(path), "com.apple.trash.deletiondate")
            except Exception:
                pass
        if raw:
            return self._parse_deletion_date(raw)
        return None

    def _parse_deletion_date(self, raw: bytes) -> Optional[datetime]:
        """Parse the binary plist deletion date from trash xattr."""
        # The deletion date is stored as a binary plist containing an NSDate
        # NSDate epoch is 2001-01-01
        try:
            import plistlib
            val = plistlib.loads(raw)
            if isinstance(val, datetime):
                return val
        except Exception:
            pass
        # Try as a Core Data timestamp (seconds since 2001-01-01)
        if len(raw) == 8:
            try:
                ts = struct.unpack(">d", raw)[0]
                mac_epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
                from datetime import timedelta
                return mac_epoch + timedelta(seconds=ts)
            except Exception:
                pass
        return None

    def _getxattr_ctypes(self, path: str, attr: str) -> Optional[str]:
        """Read xattr using ctypes."""
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        buf = ctypes.create_string_buffer(4096)
        path_b = path.encode("utf-8")
        attr_b = attr.encode("utf-8")
        size = libc.getxattr(path_b, attr_b, buf, 4096, 0, 0)
        if size > 0:
            return buf.raw[:size].decode("utf-8", errors="replace").rstrip("\x00")
        return None

    def _getxattr_ctypes_raw(self, path: str, attr: str) -> Optional[bytes]:
        """Read xattr raw bytes using ctypes."""
        import ctypes
        import ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        buf = ctypes.create_string_buffer(4096)
        path_b = path.encode("utf-8")
        attr_b = attr.encode("utf-8")
        size = libc.getxattr(path_b, attr_b, buf, 4096, 0, 0)
        if size > 0:
            return buf.raw[:size]
        return None

    async def _scan_via_osascript(self) -> list[RecoveredFile]:
        """Fallback: list Trash items via AppleScript when FDA is unavailable."""
        import asyncio
        files = []
        try:
            # Get trash item paths via Finder
            script = '''
            tell application "Finder"
                set trashItems to every item of trash
                set paths to {}
                repeat with anItem in trashItems
                    set end of paths to POSIX path of (anItem as alias)
                end repeat
                set AppleScript's text item delimiters to linefeed
                return paths as text
            end tell
            '''
            proc = await asyncio.create_subprocess_exec(
                "osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            paths = stdout.decode("utf-8", errors="replace").strip().splitlines()

            for path_str in paths:
                path_str = path_str.strip()
                if not path_str:
                    continue
                p = Path(path_str)
                if p.is_file():
                    rf = self._make_recovered_file(p)
                    if rf:
                        files.append(rf)
                elif p.is_dir():
                    for root, _dirs, fnames in os.walk(p):
                        for fname in fnames:
                            if fname.startswith("."):
                                continue
                            fp = Path(root) / fname
                            rf = self._make_recovered_file(fp)
                            if rf:
                                files.append(rf)
        except Exception:
            pass
        return files


# Auto-register
register_scanner(TrashScanner())
