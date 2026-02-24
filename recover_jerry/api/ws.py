"""WebSocket endpoint for live progress updates."""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.scan_manager import scan_manager
from ..services.recovery_manager import recovery_manager

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")

            if action == "subscribe_scan":
                job_id = msg.get("job_id")
                if job_id:
                    async def scan_cb(job):
                        await manager.broadcast({
                            "type": "scan_progress",
                            "job_id": job.id,
                            "status": job.status.value,
                            "progress": job.progress.model_dump(),
                        })
                    scan_manager.add_progress_listener(job_id, scan_cb)

            elif action == "subscribe_recovery":
                job_id = msg.get("job_id")
                if job_id:
                    async def recovery_cb(job):
                        await manager.broadcast({
                            "type": "recovery_progress",
                            "job_id": job.id,
                            "status": job.status.value,
                            "progress": job.progress.model_dump(),
                        })
                    recovery_manager.add_progress_listener(job_id, recovery_cb)

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
