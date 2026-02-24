"""Recovery job lifecycle."""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable

from ..models.recovery import (
    RecoveryJob,
    RecoveryRequest,
    RecoveryStatus,
    RecoveryProgress,
)
from ..recovery.engine import RecoveryEngine
from .scan_manager import scan_manager


class RecoveryManager:
    def __init__(self):
        self._jobs: dict[str, RecoveryJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._progress_listeners: dict[str, list[Callable]] = {}

    def create_job(self, request: RecoveryRequest) -> RecoveryJob:
        job = RecoveryJob(request=request)
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[RecoveryJob]:
        return self._jobs.get(job_id)

    def add_progress_listener(self, job_id: str, callback: Callable) -> None:
        self._progress_listeners.setdefault(job_id, []).append(callback)

    def remove_progress_listener(self, job_id: str, callback: Callable) -> None:
        listeners = self._progress_listeners.get(job_id, [])
        if callback in listeners:
            listeners.remove(callback)

    async def start_recovery(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        task = asyncio.create_task(self._run_recovery(job))
        self._tasks[job_id] = task

    async def _run_recovery(self, job: RecoveryJob) -> None:
        job.status = RecoveryStatus.RUNNING
        await self._notify_progress(job)

        # Gather the actual files from scan results
        scan_files = scan_manager.get_results(job.request.job_id)
        file_map = {f.id: f for f in scan_files}
        files_to_recover = [
            file_map[fid] for fid in job.request.file_ids if fid in file_map
        ]

        job.progress = RecoveryProgress(
            files_total=len(files_to_recover),
            bytes_total=sum(f.metadata.size for f in files_to_recover),
        )
        await self._notify_progress(job)

        engine = RecoveryEngine(
            destination=job.request.destination,
            preserve_structure=job.request.preserve_directory_structure,
            verify_checksums=job.request.verify_checksums,
        )

        try:
            async for result in engine.recover_files(files_to_recover):
                job.results.append(result)
                if result.success:
                    job.progress.files_recovered += 1
                else:
                    job.progress.files_failed += 1
                job.progress.current_file = result.original_path
                job.progress.percent = (
                    (job.progress.files_recovered + job.progress.files_failed)
                    / job.progress.files_total * 100
                ) if job.progress.files_total > 0 else 0
                job.progress.message = f"Recovered {job.progress.files_recovered}/{job.progress.files_total}"
                await self._notify_progress(job)

            job.status = RecoveryStatus.COMPLETED
            job.completed_at = datetime.now(tz=timezone.utc)
            job.progress.percent = 100.0
            job.progress.message = (
                f"Recovery complete. {job.progress.files_recovered} recovered, "
                f"{job.progress.files_failed} failed."
            )
            await self._notify_progress(job)

        except asyncio.CancelledError:
            job.status = RecoveryStatus.CANCELLED
            await self._notify_progress(job)
        except Exception as e:
            job.status = RecoveryStatus.FAILED
            job.error = str(e)
            await self._notify_progress(job)

    async def _notify_progress(self, job: RecoveryJob) -> None:
        listeners = self._progress_listeners.get(job.id, [])
        for cb in listeners:
            try:
                await cb(job)
            except Exception:
                pass


# Singleton
recovery_manager = RecoveryManager()
