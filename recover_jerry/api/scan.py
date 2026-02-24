"""Scan API endpoints."""

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.common import FileMetadata, RecoveredFile
from ..models.scan import ScanConfig, ScanJob, ScanStatus, ScanProgress
from ..services.scan_manager import scan_manager

router = APIRouter(prefix="/scan", tags=["scan"])

PHOTOREC_OUTPUT_DIR = "/tmp/recover-jerry-carve"


@router.post("/start")
async def start_scan(config: ScanConfig):
    job = scan_manager.create_job(config)
    await scan_manager.start_scan(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
async def get_scan_job(job_id: str):
    job = scan_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_scan(job_id: str):
    success = await scan_manager.cancel_scan(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan job not found or already finished")
    return {"cancelled": True}


@router.post("/load-photorec")
async def load_photorec_results():
    """Load results from a PhotoRec scan that was run externally."""
    output_path = Path(PHOTOREC_OUTPUT_DIR)
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="No PhotoRec output found at /tmp/recover-jerry-carve")

    # Create a scan job for these results
    config = ScanConfig(sources=["file_carving"])
    job = scan_manager.create_job(config)
    job.status = ScanStatus.COMPLETED
    job.completed_at = datetime.now()

    files = []
    for d in sorted(output_path.iterdir()):
        if not d.is_dir() or not d.name.startswith("recup_dir"):
            continue
        for fpath in sorted(d.iterdir()):
            if not fpath.is_file() or fpath.name.startswith("."):
                continue
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
                source_id="file_carving",
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

    scan_manager._results[job.id] = files
    job.progress = ScanProgress(
        files_found=len(files),
        sources_completed=1,
        sources_total=1,
        percent=100.0,
        message=f"Loaded {len(files)} carved files from PhotoRec",
    )

    return {"job_id": job.id, "files_loaded": len(files)}
