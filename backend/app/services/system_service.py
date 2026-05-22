"""Service for checking GPU and system status."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..core.config import settings


def get_gpu_info() -> list[dict]:
    """Query nvidia-smi for GPU information."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append(
                    {
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_mb": int(parts[2]),
                        "memory_used_mb": int(parts[3]),
                        "memory_free_mb": int(parts[4]),
                        "utilization_percent": int(parts[5]),
                    }
                )
        return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def check_weights_status() -> dict:
    """Check if model weights are downloaded."""
    weights_path = Path(settings.model_weights_dir)
    exists = weights_path.exists()

    total_size_gb = 0.0
    if exists:
        total_size = sum(f.stat().st_size for f in weights_path.rglob("*") if f.is_file())
        total_size_gb = total_size / (1024**3)

    return {
        "path": str(weights_path),
        "exists": exists,
        "size_gb": round(total_size_gb, 2),
        "ready": exists and total_size_gb > 1.0,  # Weights should be ~9GB
    }


def check_mber_cli() -> dict:
    """Check if mber-vhh CLI is available."""
    cli_path = settings.mber_cli_path
    found = shutil.which(cli_path) is not None

    # Also check in the repo path
    repo_cli = Path(settings.mber_repo_path) / cli_path
    if not found and repo_cli.exists():
        found = True

    return {
        "cli_path": cli_path,
        "available": found,
        "repo_path": settings.mber_repo_path,
        "repo_exists": Path(settings.mber_repo_path).exists(),
    }


def get_system_status() -> dict:
    """Get overall system readiness status."""
    gpus = get_gpu_info()
    weights = check_weights_status()
    cli = check_mber_cli()

    ready = bool(gpus) and weights["ready"] and cli["available"]

    return {
        "ready": ready,
        "gpus": gpus,
        "weights": weights,
        "cli": cli,
    }
