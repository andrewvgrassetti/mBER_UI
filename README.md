# mBER UI

A web-based user interface for **mBER** (Manifold Binder Engineering and Refinement) — a VHH nanobody binder design tool.

## Architecture

```
mBER_UI/
├── backend/          # Python FastAPI server
│   ├── app/
│   │   ├── core/     # Configuration
│   │   ├── models/   # Pydantic models
│   │   ├── routers/  # API endpoints + WebSocket
│   │   └── services/ # Business logic (job mgmt, GPU status)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── pages/    # JobSubmit, Dashboard, Results, Settings
│   │   ├── hooks/    # WebSocket streaming hook
│   │   ├── lib/      # API client, utilities
│   │   └── components/
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml
```

## Prerequisites

- **mber-open** repository cloned (e.g., at `/home/ubuntu/mber-open/mber-open`)
- **mber conda environment** with `mber-vhh` CLI installed (`pip install -e protocols` inside the mber env)
- NVIDIA GPU with 32GB+ VRAM
- Model weights downloaded (~9GB) via `bash download_weights.sh` (installs to `~/.mber`)
- Python 3.11+ (for backend venv)
- Node.js 20+ (for frontend)

## Setup (one-time)

### 0. Apply HMMER 3.4 / BioPython compatibility patches (one-time setup)

The `src/mber/patches/nbb2_compat.py` module contains monkey-patches that fix
anarci and ImmuneBuilder incompatibilities introduced by HMMER 3.4.  Apply them
by adding the following import at the **top** of mber-open's
`src/mber/models/folding/nbb2_model.py` (before any ImmuneBuilder imports):

```python
import mber.patches.nbb2_compat  # noqa: F401  – apply HMMER 3.4 / BioPython patches
```

Alternatively, run the patches once from the command line before launching
`mber-vhh`:

```bash
conda activate mber
python -c "import mber.patches.nbb2_compat"
mber-vhh ...
```

### 1. Install mber-vhh CLI (one-time setup)

```bash
cd /home/ubuntu/mber-open/mber-open
conda activate mber
pip install -e protocols
which mber-vhh  # Note this path for .env
conda deactivate
```

### 2. Download model weights (one-time setup)

```bash
cd /home/ubuntu/mber-open/mber-open
bash download_weights.sh
# Weights install to ~/.mber
```

### 3. Backend setup

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure .env

```bash
cp .env.example .env
nano .env
```

Set the following values:

```
MBER_UI_MBER_CLI_PATH=/home/ubuntu/miniconda3/envs/mber/bin/mber-vhh
MBER_UI_MBER_REPO_PATH=/home/ubuntu/mber-open/mber-open
MBER_UI_JOBS_DIR=./jobs
MBER_UI_MODEL_WEIGHTS_DIR=/home/ubuntu/.mber
MBER_UI_DEFAULT_GPU_DEVICE=0
MBER_UI_HOST=0.0.0.0
MBER_UI_PORT=8000
MBER_UI_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`.

## Running the App

Start the backend:

```bash
cd ~/GitRepos/mBER_UI/backend
source venv/bin/activate
nohup uvicorn app.main:app --port 8000 > uvicorn.log 2>&1 &
```

Start the frontend:

```bash
cd ~/GitRepos/mBER_UI/frontend
npm install   # first time only
nohup npm run dev > frontend.log 2>&1 &
```

Open http://localhost:5173 in your browser.

## Deploying Code Changes

```bash
cd ~/GitRepos/mBER_UI
git pull

# Restart backend
pkill -f "uvicorn app.main:app"
cd backend && source venv/bin/activate
nohup uvicorn app.main:app --port 8000 > uvicorn.log 2>&1 &

# Restart frontend (only if frontend files changed)
pkill -f "npm run dev"
cd ../frontend
nohup npm run dev > frontend.log 2>&1 &
```

## Monitoring

```bash
# Check if backend is running
pgrep -fa uvicorn

# Follow backend logs
tail -f ~/GitRepos/mBER_UI/backend/uvicorn.log

# Check running/pending jobs
curl -s http://localhost:8000/jobs | python3 -c "
import json, sys
for j in json.load(sys.stdin):
    if j['status'] in ('running', 'pending'):
        print(f\"{j['id']} - {j['target_name']} - {j['status']}\")
"

# Check job output directories
cat jobs/<job-id>/output.log
ls jobs/<job-id>/output/
```

## Development Mode

For active development, you can use `--reload` to auto-restart the backend on code changes:

```bash
uvicorn app.main:app --reload --port 8000
```

> **⚠️ Warning:** Do not use `--reload` when running mBER jobs — file writes (logs, CSVs, PDBs) to `backend/jobs/` trigger uvicorn restarts that kill running processes.

## Running Overnight Jobs

### Why there's a CPU keep-alive

mBER protein design jobs are GPU-intensive — the CPU stays nearly idle while the GPU does all the work. On AWS EC2, a CloudWatch alarm monitors CPU utilization and automatically **stops the instance** when it drops below ~5-10% for a sustained period (typically 15 minutes). This would kill any running overnight jobs.

The backend includes an automatic CPU keep-alive that generates lightweight CPU activity (~10-15% utilization on a single core) whenever jobs are queued or running. This prevents the CloudWatch alarm from firing without affecting GPU performance or memory.

### It's fully automatic

No extra steps are needed. Just start the backend and submit your jobs — the keep-alive activates when a job is enqueued and stops when all jobs finish. You'll see log messages like:

```
INFO: CPU keep-alive STARTED (preventing CloudWatch low-CPU alarm)
INFO: CPU keep-alive STOPPED (no active jobs)
```

## Quick Start (Docker)

```bash
# Set path to your mber-open clone
export MBER_REPO_PATH=/home/ubuntu/mber-open

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Configuration

All configuration is via environment variables (prefix `MBER_UI_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MBER_UI_MBER_CLI_PATH` | `mber-vhh` | Full path to the mber-vhh executable |
| `MBER_UI_MBER_REPO_PATH` | `/home/ubuntu/mber-open` | Path to the mber-open repo |
| `MBER_UI_JOBS_DIR` | `./jobs` | Directory for job data |
| `MBER_UI_MODEL_WEIGHTS_DIR` | `/home/ubuntu/mber-open/weights` | Model weights path |
| `MBER_UI_DEFAULT_GPU_DEVICE` | `0` | Default GPU index |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs` | Submit a new design job |
| `GET` | `/jobs` | List all jobs |
| `GET` | `/jobs/{id}` | Get job details + progress |
| `GET` | `/jobs/{id}/results` | Parsed accepted.csv as JSON |
| `GET` | `/jobs/{id}/files/{name}` | Download output PDB files |
| `GET` | `/jobs/{id}/log` | Get job log output |
| `DELETE` | `/jobs/{id}` | Cancel a running job |
| `WS` | `/jobs/{id}/stream` | Real-time log + progress streaming |
| `GET` | `/system/status` | GPU, weights, CLI readiness |
| `GET` | `/health` | Health check |

## Features

- **Job Submission**: Upload PDB, specify chains/hotspots, configure design parameters
- **Real-time Monitoring**: WebSocket-based live progress tracking
- **Results Viewer**: Sort/filter accepted designs by iPTM and pLDDT scores
- **System Status**: GPU memory monitoring, weight/CLI availability checks
- **Resume Support**: mBER natively supports resuming from existing `accepted.csv`

## License

This project is licensed under the terms specified in this repository.
