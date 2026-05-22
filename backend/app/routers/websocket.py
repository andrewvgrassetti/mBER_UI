"""WebSocket endpoint for real-time job log streaming."""

import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import job_service
from ..core.config import settings

router = APIRouter(tags=["websocket"])

_JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{8}$")


@router.websocket("/jobs/{job_id}/stream")
async def job_log_stream(websocket: WebSocket, job_id: str):
    """Stream job logs and progress updates via WebSocket."""
    await websocket.accept()

    if not _JOB_ID_PATTERN.match(job_id):
        await websocket.send_json({"error": "Invalid job ID"})
        await websocket.close()
        return

    job = job_service.get_job(job_id)
    if not job:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return

    log_path = Path(settings.jobs_dir).resolve() / job_id / "output.log"
    last_position = 0

    try:
        while True:
            # Send progress update
            current_job = job_service.get_job(job_id)
            if current_job:
                await websocket.send_json(
                    {
                        "type": "progress",
                        "data": {
                            "status": current_job.status.value,
                            "accepted_count": current_job.progress.accepted_count,
                            "total_trajectories": current_job.progress.total_trajectories,
                            "target_accepted": current_job.progress.target_accepted,
                        },
                    }
                )

            # Send new log lines
            if log_path.exists():
                with open(log_path, "r") as f:
                    f.seek(last_position)
                    new_content = f.read()
                    if new_content:
                        await websocket.send_json(
                            {"type": "log", "data": new_content}
                        )
                    last_position = f.tell()

            # Check if job is done
            if current_job and current_job.status.value in (
                "completed",
                "failed",
                "cancelled",
            ):
                await websocket.send_json(
                    {"type": "done", "data": {"status": current_job.status.value}}
                )
                break

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
