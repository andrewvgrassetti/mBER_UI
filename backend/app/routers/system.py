"""System status and configuration routes."""

from fastapi import APIRouter

from ..services import system_service
from ..core.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def get_system_status():
    """Get GPU, weights, and CLI status."""
    return system_service.get_system_status()


@router.get("/gpus")
async def get_gpus():
    """Get available GPUs."""
    return system_service.get_gpu_info()


@router.get("/config")
async def get_config():
    """Get current configuration (non-sensitive)."""
    return {
        "mber_repo_path": settings.mber_repo_path,
        "model_weights_dir": settings.model_weights_dir,
        "default_gpu_device": settings.default_gpu_device,
        "default_num_accepted": settings.default_num_accepted,
        "default_max_trajectories": settings.default_max_trajectories,
        "default_min_iptm": settings.default_min_iptm,
        "default_min_plddt": settings.default_min_plddt,
    }
