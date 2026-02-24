"""Results API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..services.scan_manager import scan_manager

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/{job_id}")
async def get_results(
    job_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    extension: Optional[str] = None,
    source: Optional[str] = None,
    sort_by: str = Query("filename", pattern="^(filename|size|modified|created|extension|source)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    job = scan_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")

    files = scan_manager.get_results(job_id)

    # Filter
    if search:
        search_lower = search.lower()
        files = [f for f in files if search_lower in f.filename.lower() or search_lower in f.original_path.lower()]
    if extension:
        ext = extension if extension.startswith(".") else f".{extension}"
        files = [f for f in files if f.extension.lower() == ext.lower()]
    if source:
        files = [f for f in files if f.source_id == source]

    total = len(files)

    # Sort
    sort_key_map = {
        "filename": lambda f: f.filename.lower(),
        "size": lambda f: f.metadata.size,
        "modified": lambda f: f.metadata.modified or f.metadata.created or "",
        "created": lambda f: f.metadata.created or "",
        "extension": lambda f: f.extension.lower(),
        "source": lambda f: f.source_id,
    }
    key_fn = sort_key_map.get(sort_by, sort_key_map["filename"])
    reverse = sort_order == "desc"
    try:
        files = sorted(files, key=key_fn, reverse=reverse)
    except TypeError:
        pass

    # Paginate
    page = files[offset:offset + limit]

    return {
        "job_id": job_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "files": page,
    }


@router.get("/{job_id}/stats")
async def get_result_stats(job_id: str):
    job = scan_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return scan_manager.get_result_stats(job_id)
