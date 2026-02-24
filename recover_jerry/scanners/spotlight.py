"""Spotlight (mdfind) scanner — browse files from a date range and find deleted ones."""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig
from ..models.system import SourceAvailability
from .base import BaseScanner
from .registry import register_scanner

# Only scan these directories under $HOME — actual user file locations
USER_DIRS = (
    "Desktop",
    "Documents",
    "Downloads",
    "Pictures",
    "Movies",
    "Music",
    "Public",
    "Sites",
    "projects",
)

# Always skip even within allowed dirs
SKIP_CONTAINS = (
    "/node_modules/",
    "/.git/",
    "/__pycache__/",
    "/.venv/",
    "/.npm/",
    "/.cache/",
    "/DerivedData/",
    "/.next/",
    "/.nuxt/",
    "/dist/",
    "/build/",
    "/.DS_Store",
)


class SpotlightScanner(BaseScanner):
    source_id = "spotlight"
    name = "Spotlight Index"
    description = "Browse files from a date range via Spotlight (includes existing files to help identify what's missing)"

    @property
    def requires_sudo(self) -> bool:
        return False

    async def check_availability(self) -> SourceAvailability:
        try:
            proc = await asyncio.create_subprocess_exec(
                "mdutil", "-s", "/",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            enabled = "Indexing enabled" in stdout.decode()
        except Exception:
            enabled = False

        return SourceAvailability(
            source_id=self.source_id,
            name=self.name,
            available=enabled,
            requires_sudo=False,
            detail="Spotlight indexing is active — can browse files by date" if enabled else "Spotlight indexing may be disabled",
        )

    async def scan(
        self,
        config: ScanConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[RecoveredFile]:
        if progress_callback:
            progress_callback("Querying Spotlight index...")

        # Build mdfind query
        query_parts = []
        if config.date_range:
            start_str = config.date_range.start.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = config.date_range.end.strftime("%Y-%m-%dT%H:%M:%S")
            query_parts.append(
                f'(kMDItemContentModificationDate >= "$time.iso({start_str})"'
                f' && kMDItemContentModificationDate <= "$time.iso({end_str})")'
            )
        else:
            query_parts.append('kMDItemContentModificationDate >= "$time.this_month(-6)"')

        if config.file_extensions:
            ext_conditions = []
            for ext in config.file_extensions:
                ext_clean = ext.lstrip(".")
                ext_conditions.append(f'kMDItemFSName == "*.{ext_clean}"')
            query_parts.append("(" + " || ".join(ext_conditions) + ")")

        query = " && ".join(query_parts)
        home = Path.home()

        # Search only real user directories
        search_dirs = []
        for d in USER_DIRS:
            p = home / d
            if p.exists():
                search_dirs.append(str(p))

        if not search_dirs:
            search_dirs = [str(home)]

        count = 0
        for search_dir in search_dirs:
            dir_name = Path(search_dir).name
            if progress_callback:
                progress_callback(f"Searching {dir_name}...")

            try:
                proc = await asyncio.create_subprocess_exec(
                    "mdfind", "-onlyin", search_dir, query,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                paths = stdout.decode("utf-8", errors="replace").strip().splitlines()

                for path_str in paths:
                    path_str = path_str.strip()
                    if not path_str:
                        continue

                    if self._should_skip(path_str):
                        continue

                    p = Path(path_str)
                    exists = p.exists()
                    is_file = p.is_file() if exists else True

                    if not is_file:
                        continue

                    if exists:
                        rf = self._make_from_existing(p)
                    else:
                        rf = await self._make_from_deleted(path_str)

                    if rf:
                        count += 1
                        if count % 100 == 0 and progress_callback:
                            progress_callback(f"Processing... {count} files found")
                        yield rf

            except asyncio.TimeoutError:
                if progress_callback:
                    progress_callback(f"Spotlight search timed out for {dir_name}")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Spotlight error in {dir_name}: {e}")

        if progress_callback:
            progress_callback(f"Spotlight scan complete. {count} files found.")

    async def read_file_bytes(self, file: RecoveredFile) -> Optional[bytes]:
        try:
            p = Path(file.access_path)
            if p.exists() and p.is_file():
                return p.read_bytes()
        except (PermissionError, OSError):
            pass
        return None

    def _should_skip(self, path_str: str) -> bool:
        """Filter out build artifacts and junk."""
        for substr in SKIP_CONTAINS:
            if substr in path_str:
                return True
        # Skip hidden directories (but not hidden leaf files)
        parts = path_str.split("/")
        for part in parts[:-1]:
            if part.startswith(".") and part not in (".", ".."):
                return True
        return False

    def _make_from_existing(self, path: Path) -> Optional[RecoveredFile]:
        """Create RecoveredFile from an existing file."""
        try:
            stat = path.stat()
        except (OSError, PermissionError):
            return None

        if stat.st_size == 0:
            return None

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
            original_path=str(path),
            filename=path.name,
            extension=ext,
            metadata=FileMetadata(
                size=stat.st_size,
                created=created,
                modified=modified,
            ),
            access_path=str(path),
        )

    async def _make_from_deleted(self, path_str: str) -> Optional[RecoveredFile]:
        """Create RecoveredFile from a Spotlight result for a deleted file."""
        p = Path(path_str)
        metadata = await self._get_spotlight_metadata(path_str)
        ext = p.suffix.lower() if p.suffix else ""

        return RecoveredFile(
            source_id="spotlight_deleted",
            original_path=path_str,
            filename=p.name,
            extension=ext,
            metadata=FileMetadata(
                size=metadata.get("size", 0),
                created=metadata.get("created"),
                modified=metadata.get("modified"),
            ),
            access_path="",
        )

    @staticmethod
    def _parse_mdls_date(val: str) -> Optional[datetime]:
        """Parse date strings from mdls output, handling multiple formats."""
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %Z"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        # Last resort: strip timezone and parse as UTC
        try:
            dt = datetime.strptime(val[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    async def _get_spotlight_metadata(self, path_str: str) -> dict:
        result = {}
        try:
            proc = await asyncio.create_subprocess_exec(
                "mdls",
                "-name", "kMDItemFSSize",
                "-name", "kMDItemContentCreationDate",
                "-name", "kMDItemContentModificationDate",
                path_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            for line in stdout.decode().splitlines():
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip('"')
                if val and val != "(null)":
                    key = key.strip()
                    if "Size" in key:
                        try:
                            result["size"] = int(val)
                        except ValueError:
                            pass
                    elif "CreationDate" in key:
                        result["created"] = self._parse_mdls_date(val)
                    elif "ModificationDate" in key:
                        result["modified"] = self._parse_mdls_date(val)
        except Exception:
            pass
        return result


register_scanner(SpotlightScanner())
