"""System info API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.system_inspector import inspect_system
from ..scanners.file_carving import set_sudo_password, get_sudo_password, _test_sudo

router = APIRouter(prefix="/system", tags=["system"])

_cached_info = None


class SudoRequest(BaseModel):
    password: str


@router.get("/info")
async def get_system_info():
    global _cached_info
    if _cached_info is None:
        _cached_info = await inspect_system()
    return _cached_info


@router.post("/refresh")
async def refresh_system_info():
    global _cached_info
    _cached_info = await inspect_system()
    return _cached_info


@router.post("/sudo")
async def authenticate_sudo(req: SudoRequest):
    """Validate and store sudo password for the session."""
    valid = await _test_sudo(req.password)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid sudo password")
    set_sudo_password(req.password)
    # Refresh system info to update source availability
    global _cached_info
    _cached_info = await inspect_system()
    return {"authenticated": True}


@router.get("/sudo/status")
async def sudo_status():
    return {"authenticated": get_sudo_password() is not None}
