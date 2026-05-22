"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # Paths
    mber_cli_path: str = "mber-vhh"
    mber_repo_path: str = "/home/ubuntu/mber-open"
    jobs_dir: str = "./jobs"
    model_weights_dir: str = "/home/ubuntu/mber-open/weights"

    # GPU
    default_gpu_device: int = 0

    # Default design parameters
    default_num_accepted: int = 100
    default_max_trajectories: int = 10000
    default_min_iptm: float = 0.75
    default_min_plddt: float = 0.70

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_prefix = "MBER_UI_"


settings = Settings()
