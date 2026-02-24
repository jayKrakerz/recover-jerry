"""Scan job lifecycle and async orchestration."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Callable

from ..models.scan import ScanConfig, ScanJob, ScanStatus, ScanProgress, ScanResult
from ..models.common import RecoveredFile
from ..scanners.registry import get_scanner
from ..services.date_filter import file_matches_date_range

logger = logging.getLogger(__name__)


class ScanManager:
    def __init__(self):
        self._jobs: dict[str, ScanJob] = {}
        self._results: dict[str, list[RecoveredFile]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._progress_listeners: dict[str, list[Callable]] = {}

    def create_job(self, config: ScanConfig) -> ScanJob:
        job = ScanJob(config=config)
        self._jobs[job.id] = job
        self._results[job.id] = []
        return job

    def get_job(self, job_id: str) -> Optional[ScanJob]:
        return self._jobs.get(job_id)

    def get_results(self, job_id: str) -> list[RecoveredFile]:
        return self._results.get(job_id, [])

    def add_progress_listener(self, job_id: str, callback: Callable) -> None:
        self._progress_listeners.setdefault(job_id, []).append(callback)

    def remove_progress_listener(self, job_id: str, callback: Callable) -> None:
        listeners = self._progress_listeners.get(job_id, [])
        if callback in listeners:
            listeners.remove(callback)

    async def start_scan(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        task = asyncio.create_task(self._run_scan(job))
        self._tasks[job_id] = task

    async def cancel_scan(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        job = self._jobs.get(job_id)
        if task and job:
            task.cancel()
            job.status = ScanStatus.CANCELLED
            await self._notify_progress(job)
            # Clean up any running scanner processes
            for source_id in job.config.sources:
                scanner = get_scanner(source_id)
                if scanner and hasattr(scanner, 'cleanup'):
                    try:
                        await scanner.cleanup()
                    except Exception:
                        pass
            return True
        return False

    async def _run_scan(self, job: ScanJob) -> None:
        job.status = ScanStatus.RUNNING
        job.progress = ScanProgress(
            sources_total=len(job.config.sources),
        )
        await self._notify_progress(job)

        try:
            for i, source_id in enumerate(job.config.sources):
                scanner = get_scanner(source_id)
                if not scanner:
                    continue

                job.progress.current_source = scanner.name
                job.progress.sources_completed = i + 1
                job.progress.percent = ((i + 1) / len(job.config.sources)) * 100
                job.progress.message = f"Scanning {scanner.name}..."
                await self._notify_progress(job)

                last_notify_time = 0

                def progress_cb(msg: str):
                    job.progress.message = msg
                    logger.info(f"[{scanner.name}] {msg}")

                file_count = 0
                filtered_date = 0
                filtered_type = 0
                # Carved files don't have meaningful timestamps — skip date filter
                skip_date_filter = (source_id == "file_carving")
                logger.info(f"[{scanner.name}] Starting scan... (skip_date_filter={skip_date_filter})")
                async for file in scanner.scan(job.config, progress_cb):
                    file_count += 1
                    # Apply date filter (skip for file carving)
                    if skip_date_filter or file_matches_date_range(file, job.config.date_range):
                        # Apply file type/extension filters
                        if self._matches_filters(file, job.config):
                            self._results[job.id].append(file)
                            job.progress.files_found = len(self._results[job.id])
                            # Throttle WS notifications: max once per 5 seconds
                            now = time.monotonic()
                            if now - last_notify_time >= 5.0:
                                last_notify_time = now
                                await self._notify_progress(job)
                        else:
                            filtered_type += 1
                    else:
                        filtered_date += 1
                # Always notify at end of each source
                await self._notify_progress(job)
                logger.info(
                    f"[{scanner.name}] Done: {file_count} yielded, "
                    f"{filtered_date} filtered by date, {filtered_type} filtered by type, "
                    f"{job.progress.files_found} kept"
                )

            job.status = ScanStatus.COMPLETED
            job.completed_at = datetime.now(tz=timezone.utc)
            job.progress.sources_completed = len(job.config.sources)
            job.progress.percent = 100.0
            job.progress.message = f"Scan complete. Found {job.progress.files_found} files."
            await self._notify_progress(job)

        except asyncio.CancelledError:
            job.status = ScanStatus.CANCELLED
            await self._notify_progress(job)
        except Exception as e:
            job.status = ScanStatus.FAILED
            job.error = str(e)
            await self._notify_progress(job)

    def _matches_filters(self, file: RecoveredFile, config: ScanConfig) -> bool:
        """Check file type and extension filters."""
        if config.file_extensions:
            normalized = [ext if ext.startswith(".") else f".{ext}" for ext in config.file_extensions]
            if file.extension.lower() not in normalized:
                return False

        if config.file_types:
            mime = (file.metadata.mime_type or "").lower()
            for ft in config.file_types:
                ft = ft.lower()
                if ft == "image" and file.extension in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff", ".bmp", ".svg"):
                    break
                if ft == "document" and file.extension in (".pdf", ".doc", ".docx", ".txt", ".rtf", ".pages", ".odt", ".xls", ".xlsx", ".csv"):
                    break
                if ft == "video" and file.extension in (".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v"):
                    break
                if ft == "audio" and file.extension in (".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"):
                    break
                if ft == "code" and file.extension in (".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".md", ".sh", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".swift"):
                    break
            else:
                return False

        return True

    async def _notify_progress(self, job: ScanJob) -> None:
        listeners = self._progress_listeners.get(job.id, [])
        for cb in listeners:
            try:
                await cb(job)
            except Exception:
                pass

    def get_result_stats(self, job_id: str) -> dict:
        files = self._results.get(job_id, [])
        total_size = sum(f.metadata.size for f in files)
        by_source = {}
        by_extension = {}
        for f in files:
            by_source[f.source_id] = by_source.get(f.source_id, 0) + 1
            ext = f.extension or "(no ext)"
            by_extension[ext] = by_extension.get(ext, 0) + 1

        return {
            "total_files": len(files),
            "total_size": total_size,
            "by_source": by_source,
            "by_extension": by_extension,
        }


# Singleton
scan_manager = ScanManager()
