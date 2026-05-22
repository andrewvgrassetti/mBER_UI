"""Job-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSubmission(BaseModel):
    """Request body for submitting a new design job."""

    target_name: Optional[str] = None
    pdb_code: Optional[str] = None  # Alternative to file upload
    target_chains: str = Field(..., description="Comma-separated chain IDs, e.g. 'A' or 'A,B'")
    hotspot_residues: Optional[str] = Field(None, description="e.g. 'A56' or 'A56,B20'")
    num_accepted: int = 100
    max_trajectories: int = 10000
    min_iptm: float = 0.75
    min_plddt: float = 0.70
    masked_vhh_sequence: Optional[str] = None
    skip_animations: bool = False
    skip_pickle: bool = True
    skip_png: bool = False
    gpu_device: int = 0


class JobProgress(BaseModel):
    """Real-time progress information for a running job."""

    accepted_count: int = 0
    total_trajectories: int = 0
    target_accepted: int = 100
    max_trajectories: int = 10000


class JobResponse(BaseModel):
    """Full job information returned by the API."""

    id: str
    target_name: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress: JobProgress
    error_message: Optional[str] = None
    settings_path: Optional[str] = None
    output_dir: Optional[str] = None


class JobListItem(BaseModel):
    """Summary job info for the jobs list."""

    id: str
    target_name: str
    status: JobStatus
    created_at: datetime
    progress: JobProgress


class DesignResult(BaseModel):
    """A single accepted design from accepted.csv."""

    index: int
    sequence: str
    iptm: float
    plddt: float
    pdb_filename: Optional[str] = None
    additional_metrics: dict = Field(default_factory=dict)
