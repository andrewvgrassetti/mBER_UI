"""Job management API routes."""

import os
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from ..models.job import JobSubmission, JobResponse, JobListItem, DesignResult
from ..services import job_service
from ..core.config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Pattern for safe filenames
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,254}$")


@router.post("", response_model=dict)
async def submit_job(
    target_chains: str = Form(...),
    pdb_file: UploadFile | None = File(None),
    pdb_code: str | None = Form(None),
    target_name: str | None = Form(None),
    hotspot_residues: str | None = Form(None),
    num_accepted: int = Form(100),
    max_trajectories: int = Form(10000),
    min_iptm: float = Form(0.75),
    min_plddt: float = Form(0.70),
    masked_vhh_sequence: str | None = Form(None),
    skip_animations: bool = Form(False),
    skip_pickle: bool = Form(True),
    skip_png: bool = Form(False),
    gpu_device: int = Form(0),
):
    """Submit a new mBER design job."""
    # Handle PDB input
    if pdb_file and pdb_file.filename:
        # Validate and sanitize filename
        filename = Path(pdb_file.filename).name
        if not _SAFE_FILENAME.match(filename):
            raise HTTPException(status_code=400, detail="Invalid filename")
        # Save uploaded PDB
        upload_dir = Path(settings.jobs_dir).resolve() / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        pdb_path = str(upload_dir / filename)
        with open(pdb_path, "wb") as f:
            content = await pdb_file.read()
            f.write(content)
        if not target_name:
            target_name = Path(filename).stem
    elif pdb_code:
        # mBER's process_target handles PDB codes natively (downloads from RCSB)
        pdb_path = pdb_code.upper()
        if not target_name:
            target_name = pdb_code.upper()
    else:
        raise HTTPException(status_code=400, detail="Either pdb_file or pdb_code is required")

    submission = JobSubmission(
        target_name=target_name,
        pdb_code=pdb_code,
        target_chains=target_chains,
        hotspot_residues=hotspot_residues,
        num_accepted=num_accepted,
        max_trajectories=max_trajectories,
        min_iptm=min_iptm,
        min_plddt=min_plddt,
        masked_vhh_sequence=masked_vhh_sequence,
        skip_animations=skip_animations,
        skip_pickle=skip_pickle,
        skip_png=skip_png,
        gpu_device=gpu_device,
    )

    job_id = await job_service.create_job(submission, pdb_path)
    return {"job_id": job_id, "status": "submitted"}


@router.get("", response_model=list[JobListItem])
async def list_jobs():
    """List all jobs."""
    return job_service.list_jobs()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job details."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/results", response_model=list[DesignResult])
async def get_results(job_id: str):
    """Get parsed design results from accepted.csv."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_service.get_results(job_id)


@router.get("/{job_id}/log")
async def get_job_log(job_id: str, tail: int = 100):
    """Get job log output."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    log = job_service.get_job_log(job_id, tail_lines=tail)
    return {"log": log}


@router.get("/{job_id}/files/{filename:path}")
async def get_output_file(job_id: str, filename: str):
    """Serve an output file (PDB, PNG, etc)."""
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = job_service.get_output_file_path(job_id, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    success = await job_service.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}


@router.post("/{job_id}/retry", response_model=dict)
async def retry_job(job_id: str):
    """Retry a failed or cancelled job by creating a new job with the same parameters."""
    new_job_id = await job_service.retry_job(job_id)
    if not new_job_id:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be retried. Only failed or cancelled jobs with saved parameters can be retried.",
        )
    return {"job_id": new_job_id, "status": "submitted"}
