"""Aggregate all API sub-routers."""

from fastapi import APIRouter

from . import system, scan, results, recovery, preview, ws

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(scan.router)
api_router.include_router(results.router)
api_router.include_router(recovery.router)
api_router.include_router(preview.router)
api_router.include_router(ws.router)
