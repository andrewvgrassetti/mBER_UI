"""Service for managing mBER design jobs."""

import asyncio
import csv
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


def _generate_settings_yaml(job_id: str, submission: JobSubmission, pdb_path: str) -> str:
    """Generate a mBER settings YAML for this job and return the path."""
    job_path = _job_dir(job_id)
    job_path.mkdir(parents=True, exist_ok=True)

    output_dir = str(job_path / "output")
    os.makedirs(output_dir, exist_ok=True)

    settings_dict = {
        "target": {
            "pdb_path": pdb_path,
            "name": submission.target_name or Path(pdb_path).stem,
            "chains": submission.target_chains.split(","),
        },
        "design": {
            "num_accepted": submission.num_accepted,
            "max_trajectories": submission.max_trajectories,
            "min_iptm": submission.min_iptm,
            "min_plddt": submission.min_plddt,
        },
        "output": {
            "dir": output_dir,
            "skip_animations": submission.skip_animations,
            "skip_pickle": submission.skip_pickle,
            "skip_png": submission.skip_png,
        },
        "gpu": {
            "device": submission.gpu_device,
        },
    }

    if submission.hotspot_residues:
        settings_dict["target"]["hotspot_residues"] = submission.hotspot_residues.split(",")

    if submission.masked_vhh_sequence:
        settings_dict["design"]["masked_vhh_sequence"] = submission.masked_vhh_sequence

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
    """Create a new job and start it."""
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

    # Launch the mBER process
    asyncio.create_task(_run_job(job_id, settings_path))

    return job_id


async def _run_job(job_id: str, settings_path: str) -> None:
    """Run mber-vhh as a subprocess."""
    job = _jobs[job_id]
    job["status"] = JobStatus.RUNNING
    job["updated_at"] = datetime.now(timezone.utc)

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
            job["error_message"] = f"Process exited with code {process.returncode}"
    except Exception as e:
        job["status"] = JobStatus.FAILED
        job["error_message"] = str(e)
    finally:
        job["updated_at"] = datetime.now(timezone.utc)
        _processes.pop(job_id, None)


def get_job(job_id: str) -> Optional[JobResponse]:
    """Get full job details."""
    job = _jobs.get(job_id)
    if not job:
        return None

    progress = _parse_progress(job_id, job.get("submission", {}))

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
    )


def list_jobs() -> list[JobListItem]:
    """List all jobs."""
    result = []
    for job_id, job in _jobs.items():
        progress = _parse_progress(job_id, job.get("submission", {}))
        result.append(
            JobListItem(
                id=job["id"],
                target_name=job["target_name"],
                status=job["status"],
                created_at=job["created_at"],
                progress=progress,
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
    """Cancel a running job."""
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
