"""File preview API endpoint."""

import mimetypes
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import settings
from ..scanners.registry import get_scanner
from ..services.scan_manager import scan_manager

router = APIRouter(prefix="/preview", tags=["preview"])


@router.get("/{job_id}/{file_id}")
async def preview_file(job_id: str, file_id: str):
    job = scan_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    files = scan_manager.get_results(job_id)
    file = next((f for f in files if f.id == file_id), None)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Size check
    if file.metadata.size > settings.max_preview_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large for preview")

    scanner = get_scanner(file.source_id)
    if not scanner:
        raise HTTPException(status_code=500, detail="Scanner not available")

    data = await scanner.read_file_bytes(file)
    if data is None:
        raise HTTPException(status_code=404, detail="Could not read file")

    mime_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

    return Response(
        content=data,
        media_type=mime_type,
        headers={"Content-Disposition": f'inline; filename="{file.filename}"'},
    )
