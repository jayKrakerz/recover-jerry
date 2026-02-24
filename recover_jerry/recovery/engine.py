"""Copy files to destination with verification."""

import hashlib
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

from ..models.common import RecoveredFile
from ..models.recovery import RecoveryFileResult


class RecoveryEngine:
    def __init__(
        self,
        destination: str,
        preserve_structure: bool = True,
        verify_checksums: bool = True,
    ):
        self.destination = Path(destination)
        self.preserve_structure = preserve_structure
        self.verify_checksums = verify_checksums

    async def recover_files(
        self, files: list[RecoveredFile]
    ) -> AsyncIterator[RecoveryFileResult]:
        """Recover files, yielding results as each completes."""
        self.destination.mkdir(parents=True, exist_ok=True)

        for file in files:
            result = await self._recover_one(file)
            yield result

    async def _recover_one(self, file: RecoveredFile) -> RecoveryFileResult:
        """Recover a single file."""
        source = Path(file.access_path)
        result = RecoveryFileResult(
            file_id=file.id,
            original_path=file.original_path,
        )

        if not source.exists():
            result.error = f"Source file not found: {file.access_path}"
            return result

        try:
            dest_path = self._compute_dest_path(file)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle name collisions
            dest_path = self._unique_path(dest_path)

            # Compute source checksum before copy
            source_hash = None
            if self.verify_checksums:
                source_hash = self._sha256(source)

            # Copy the file
            shutil.copy2(str(source), str(dest_path))

            result.recovered_path = str(dest_path)
            result.success = True

            # Verify
            if self.verify_checksums and source_hash:
                dest_hash = self._sha256(dest_path)
                result.checksum_match = (source_hash == dest_hash)
                if not result.checksum_match:
                    result.error = "Checksum mismatch after copy"
                    result.success = False

        except PermissionError as e:
            result.error = f"Permission denied: {e}"
        except OSError as e:
            result.error = f"OS error: {e}"
        except Exception as e:
            result.error = str(e)

        return result

    def _compute_dest_path(self, file: RecoveredFile) -> Path:
        """Compute the destination path for a recovered file."""
        if self.preserve_structure and file.original_path:
            # Reconstruct directory structure relative to root
            orig = Path(file.original_path)
            # Strip leading / to make it relative
            relative = Path(str(orig).lstrip("/"))
            return self.destination / relative
        else:
            return self.destination / file.filename

    def _unique_path(self, path: Path) -> Path:
        """If path exists, add a numeric suffix."""
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def _sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
