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

- **mber-open** repository cloned (e.g., at `/home/ubuntu/mber-open`)
- NVIDIA GPU with 32GB+ VRAM
- Model weights downloaded (~9GB)
- Python 3.11+ and Node.js 20+

## Quick Start (Development)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit paths to match your setup
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

The Vite dev server proxies `/api` requests to the backend at port 8000.

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
| `MBER_UI_MBER_CLI_PATH` | `mber-vhh` | Path to the mber-vhh executable |
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
