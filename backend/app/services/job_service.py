"""Service for managing mBER design jobs."""

import asyncio
import csv
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from ..core.config import settings
from .keepalive import start_keepalive, stop_keepalive
from ..models.job import (
    DesignResult,
    JobListItem,
    JobProgress,
    JobResponse,
    JobStatus,
    JobSubmission,
)

# In-memory job registry (persisted via filesystem)
_jobs: dict[str, dict] = {}
_processes: dict[str, asyncio.subprocess.Process] = {}

# Sequential job queue — only one GPU job runs at a time
_job_queue: asyncio.Queue[str] = asyncio.Queue()
_queue_worker_task: Optional[asyncio.Task] = None

# Strict pattern for job IDs (8 hex chars)
_JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{8}$")


def _validate_job_id(job_id: str) -> bool:
    """Validate that a job ID matches the expected format."""
    return bool(_JOB_ID_PATTERN.match(job_id))


def _jobs_root() -> Path:
    p = Path(settings.jobs_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _job_dir(job_id: str) -> Path:
    if not _validate_job_id(job_id):
        raise ValueError(f"Invalid job ID: {job_id}")
    return _jobs_root() / job_id


def _save_job(job_id: str) -> None:
    """Persist job metadata to disk as JSON."""
    job = _jobs.get(job_id)
    if not job:
        return
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)
    meta_path = job_path / "job_meta.json"
    serializable = {
        "id": job["id"],
        "target_name": job["target_name"],
        "status": job["status"].value if isinstance(job["status"], JobStatus) else job["status"],
        "created_at": job["created_at"].isoformat(),
        "updated_at": job["updated_at"].isoformat(),
        "settings_path": job.get("settings_path"),
        "output_dir": job.get("output_dir"),
        "error_message": job.get("error_message"),
        "submission": job.get("submission"),
    }
    with open(meta_path, "w") as f:
        json.dump(serializable, f, indent=2)


def _load_existing_jobs() -> None:
    """Load persisted jobs from disk on startup."""
    jobs_root = _jobs_root()
    for entry in jobs_root.iterdir():
        if not entry.is_dir():
            continue
        if not _JOB_ID_PATTERN.match(entry.name):
            continue
        meta_path = entry / "job_meta.json"
        if not meta_path.exists():
            continue
        try:
            with open(meta_path, "r") as f:
                data = json.load(f)
            # Reconstruct job data
            job_data = {
                "id": data["id"],
                "target_name": data["target_name"],
                "status": JobStatus(data["status"]),
                "created_at": datetime.fromisoformat(data["created_at"]),
                "updated_at": datetime.fromisoformat(data["updated_at"]),
                "settings_path": data.get("settings_path"),
                "output_dir": data.get("output_dir"),
                "error_message": data.get("error_message"),
                "submission": data.get("submission"),
            }
            # Mark previously running/pending jobs as interrupted
            if job_data["status"] in (JobStatus.RUNNING, JobStatus.PENDING):
                job_data["status"] = JobStatus.FAILED
                job_data["error_message"] = "Job interrupted by server restart"
                job_data["updated_at"] = datetime.now(timezone.utc)
            # One-time cleanup: fix broken settings.yaml with quoted masked_sequence
            settings_path = job_data.get("settings_path")
            if settings_path and os.path.exists(settings_path):
                try:
                    with open(settings_path, "r") as sf:
                        settings_data = yaml.safe_load(sf)
                    if (
                        settings_data
                        and isinstance(settings_data.get("binder"), dict)
                        and isinstance(settings_data["binder"].get("masked_sequence"), str)
                    ):
                        seq = settings_data["binder"]["masked_sequence"]
                        cleaned = seq.strip().strip('"').strip("'")
                        if cleaned != seq:
                            settings_data["binder"]["masked_sequence"] = cleaned
                            with open(settings_path, "w") as sf:
                                yaml.dump(settings_data, sf, default_flow_style=False)
                except Exception:
                    pass  # Don't block startup for cleanup failures

            _jobs[data["id"]] = job_data
        except (json.JSONDecodeError, KeyError, ValueError):
            # Skip corrupted metadata files
            continue


def _generate_settings_yaml(job_id: str, submission: JobSubmission, pdb_path: str) -> str:
    """Generate a mBER settings YAML for this job and return the path."""
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)

    output_dir = str(job_path / "output")
    os.makedirs(output_dir, exist_ok=True)

    settings_dict = {
        "target": {
            "pdb": pdb_path,
            "name": submission.target_name or Path(pdb_path).stem,
            "chains": submission.target_chains,
            "hotspots": submission.hotspot_residues if submission.hotspot_residues else None,
        },
        "stopping": {
            "num_accepted": submission.num_accepted,
            "max_trajectories": submission.max_trajectories,
        },
        "filters": {
            "min_iptm": submission.min_iptm,
            "min_plddt": submission.min_plddt,
        },
        "output": {
            "dir": output_dir,
            "skip_animations": submission.skip_animations,
            "skip_pickle": submission.skip_pickle,
            "skip_png": submission.skip_png,
        },
    }

    if submission.masked_vhh_sequence:
        cleaned_sequence = submission.masked_vhh_sequence.strip().strip('"').strip("'")
        settings_dict["binder"] = {"masked_sequence": cleaned_sequence}

    settings_path = str(job_path / "settings.yaml")
    with open(settings_path, "w") as f:
        yaml.dump(settings_dict, f, default_flow_style=False)

    return settings_path


def _parse_progress(job_id: str, submission_data: dict) -> JobProgress:
    """Parse current progress by reading accepted.csv and runs directory."""
    job_path = _job_dir(job_id)
    output_dir = job_path / "output"
    accepted_csv = output_dir / "accepted.csv"

    accepted_count = 0
    if accepted_csv.exists():
        with open(accepted_csv, "r") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            accepted_count = sum(1 for _ in reader)

    # Count trajectory runs
    runs_dir = output_dir / "runs"
    total_trajectories = 0
    if runs_dir.exists():
        total_trajectories = len(list(runs_dir.iterdir()))

    return JobProgress(
        accepted_count=accepted_count,
        total_trajectories=total_trajectories,
        target_accepted=submission_data.get("num_accepted", 100),
        max_trajectories=submission_data.get("max_trajectories", 10000),
    )


async def create_job(submission: JobSubmission, pdb_path: str) -> str:
    """Create a new job and enqueue it for sequential execution."""
    job_id = str(uuid.uuid4())[:8]

    settings_path = _generate_settings_yaml(job_id, submission, pdb_path)

    job_data = {
        "id": job_id,
        "target_name": submission.target_name or Path(pdb_path).stem,
        "status": JobStatus.PENDING,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "settings_path": settings_path,
        "output_dir": str(_job_dir(job_id) / "output"),
        "error_message": None,
        "submission": submission.model_dump(),
    }
    _jobs[job_id] = job_data
    _save_job(job_id)

    # Enqueue for sequential processing (prevents CUDA OOM from concurrent GPU jobs)
    await _job_queue.put(job_id)

    # Ensure CPU keep-alive is running while jobs are queued/active
    start_keepalive()

    return job_id


async def _run_job(job_id: str, settings_path: str) -> None:
    """Run mber-vhh as a subprocess."""
    job = _jobs[job_id]
    job["status"] = JobStatus.RUNNING
    job["updated_at"] = datetime.now(timezone.utc)
    _save_job(job_id)

    log_path = _job_dir(job_id) / "output.log"

    try:
        cmd = [settings.mber_cli_path, "--settings", settings_path]

        with open(log_path, "w") as log_file:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                cwd=settings.mber_repo_path,
            )
            _processes[job_id] = process
            await process.wait()

        if process.returncode == 0:
            job["status"] = JobStatus.COMPLETED
        else:
            job["status"] = JobStatus.FAILED
            # Read last 50 lines of log for error context
            log_tail = ""
            if log_path.exists():
                with open(log_path, "r") as lf:
                    lines = lf.readlines()
                    log_tail = "".join(lines[-50:])
            job["error_message"] = (
                f"Process exited with code {process.returncode}\n\n"
                f"--- Last 50 lines of log ---\n{log_tail}"
            )
    except Exception as e:
        job["status"] = JobStatus.FAILED
        job["error_message"] = str(e)
    finally:
        job["updated_at"] = datetime.now(timezone.utc)
        _save_job(job_id)
        _processes.pop(job_id, None)


def get_job(job_id: str) -> Optional[JobResponse]:
    """Get full job details."""
    job = _jobs.get(job_id)
    if not job:
        return None

    progress = _parse_progress(job_id, job.get("submission") or {})

    return JobResponse(
        id=job["id"],
        target_name=job["target_name"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        progress=progress,
        error_message=job.get("error_message"),
        settings_path=job.get("settings_path"),
        output_dir=job.get("output_dir"),
        submission=job.get("submission"),
    )


def list_jobs() -> list[JobListItem]:
    """List all jobs."""
    result = []
    for job_id, job in _jobs.items():
        progress = _parse_progress(job_id, job.get("submission") or {})
        result.append(
            JobListItem(
                id=job["id"],
                target_name=job["target_name"],
                status=job["status"],
                created_at=job["created_at"],
                progress=progress,
                error_message=job.get("error_message"),
                submission=job.get("submission"),
            )
        )
    return sorted(result, key=lambda j: j.created_at, reverse=True)


def get_results(job_id: str) -> list[DesignResult]:
    """Parse accepted.csv and return design results."""
    job_path = _job_dir(job_id)
    accepted_csv = job_path / "output" / "accepted.csv"

    if not accepted_csv.exists():
        return []

    results = []
    with open(accepted_csv, "r") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Flexible parsing — mBER CSV columns may vary
            result = DesignResult(
                index=i,
                sequence=row.get("sequence", row.get("seq", "")),
                iptm=float(row.get("iptm", row.get("iPTM", 0))),
                plddt=float(row.get("plddt", row.get("pLDDT", 0))),
                pdb_filename=row.get("pdb_file", row.get("pdb", None)),
                additional_metrics={
                    k: v
                    for k, v in row.items()
                    if k not in ("sequence", "seq", "iptm", "iPTM", "plddt", "pLDDT", "pdb_file", "pdb")
                },
            )
            results.append(result)
    return results


async def cancel_job(job_id: str) -> bool:
    """Cancel a running or pending job."""
    process = _processes.get(job_id)
    if process:
        process.terminate()
        await asyncio.sleep(1)
        if process.returncode is None:
            process.kill()
        _processes.pop(job_id, None)

    job = _jobs.get(job_id)
    if job:
        job["status"] = JobStatus.CANCELLED
        job["updated_at"] = datetime.now(timezone.utc)
        _save_job(job_id)
        return True
    return False


def get_job_log(job_id: str, tail_lines: int = 100) -> str:
    """Get the tail of the job log."""
    log_path = _job_dir(job_id) / "output.log"
    if not log_path.exists():
        return ""

    with open(log_path, "r") as f:
        lines = f.readlines()
    return "".join(lines[-tail_lines:])


def get_output_file_path(job_id: str, filename: str) -> Optional[Path]:
    """Get path to an output file (PDB, etc)."""
    if not _validate_job_id(job_id):
        return None

    # Reject filenames with path traversal attempts
    if ".." in filename or filename.startswith("/"):
        return None

    job_path = _job_dir(job_id) / "output"
    file_path = (job_path / filename).resolve()

    # Security: ensure resolved path is within the output directory
    try:
        file_path.relative_to(job_path.resolve())
    except ValueError:
        return None

    if file_path.exists():
        return file_path
    return None


async def _queue_worker() -> None:
    """Process jobs sequentially from the queue (one at a time)."""
    while True:
        job_id = await _job_queue.get()
        try:
            job = _jobs.get(job_id)
            if not job:
                continue
            # Skip jobs that were cancelled while waiting in queue
            if job["status"] == JobStatus.CANCELLED:
                continue
            settings_path = job["settings_path"]
            await _run_job(job_id, settings_path)
        finally:
            _job_queue.task_done()
            # Stop keep-alive if queue is empty and no more work pending
            if _job_queue.empty():
                stop_keepalive()


async def start_queue_worker() -> None:
    """Start the background queue worker. Call during app startup."""
    global _queue_worker_task
    _load_existing_jobs()
    _queue_worker_task = asyncio.create_task(_queue_worker())


async def stop_queue_worker() -> None:
    """Stop the background queue worker. Call during app shutdown."""
    global _queue_worker_task
    if _queue_worker_task:
        _queue_worker_task.cancel()
        try:
            await _queue_worker_task
        except asyncio.CancelledError:
            pass
        _queue_worker_task = None


async def retry_job(job_id: str) -> Optional[str]:
    """Retry a failed or cancelled job by creating a new job with the same parameters."""
    job = _jobs.get(job_id)
    if not job:
        return None
    if job["status"] not in (JobStatus.FAILED, JobStatus.CANCELLED):
        return None

    submission_data = job.get("submission")
    if not submission_data:
        # Legacy job — reconstruct submission from settings.yaml
        settings_path = job.get("settings_path")
        if not settings_path or not os.path.exists(settings_path):
            return None
        with open(settings_path, "r") as f:
            settings_yaml = yaml.safe_load(f)

        target = settings_yaml.get("target", {})
        stopping = settings_yaml.get("stopping", {})
        filters = settings_yaml.get("filters", {})
        output = settings_yaml.get("output", {})
        binder = settings_yaml.get("binder", {})

        submission_data = {
            "target_name": target.get("name"),
            "pdb_code": None,
            "target_chains": target.get("chains"),
            "hotspot_residues": target.get("hotspots"),
            "num_accepted": stopping.get("num_accepted", 100),
            "max_trajectories": stopping.get("max_trajectories", 10000),
            "min_iptm": filters.get("min_iptm", 0.75),
            "min_plddt": filters.get("min_plddt", 0.70),
            "masked_vhh_sequence": binder.get("masked_sequence"),
            "skip_animations": output.get("skip_animations", False),
            "skip_pickle": output.get("skip_pickle", True),
            "skip_png": output.get("skip_png", False),
            "gpu_device": 0,
        }

    submission = JobSubmission(**submission_data)

    # Determine the PDB path from the original settings
    settings_path = job.get("settings_path")
    pdb_path = None
    if settings_path and os.path.exists(settings_path):
        with open(settings_path, "r") as f:
            settings_yaml = yaml.safe_load(f)
        pdb_path = settings_yaml.get("target", {}).get("pdb")

    if not pdb_path:
        # Fallback: use pdb_code if available
        if submission.pdb_code:
            pdb_path = submission.pdb_code.upper()
        else:
            return None

    new_job_id = await create_job(submission, pdb_path)
    return new_job_id
