"""Recovery API endpoints."""

from fastapi import APIRouter, HTTPException

from ..models.recovery import RecoveryRequest
from ..utils.permissions import check_path_writable
from ..services.recovery_manager import recovery_manager

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/start")
async def start_recovery(request: RecoveryRequest):
    # Validate destination
    if not check_path_writable(request.destination):
        raise HTTPException(status_code=400, detail="Destination is not writable")

    job = recovery_manager.create_job(request)
    await recovery_manager.start_recovery(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
async def get_recovery_job(job_id: str):
    job = recovery_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Recovery job not found")
    return job
