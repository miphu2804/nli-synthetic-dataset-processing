# NLI Synthetic Data Processing

Vietnamese README: [README.vi.md](README.vi.md)

Monorepo layout:

```text
nli-synthetic-data-processing/
├── backend/                        FastAPI + FastMCP server (Python, uv)
│   ├── src/
│   │   ├── main.py                 App entry — wires FastAPI + FastMCP
│   │   ├── app_config.py           Pydantic-settings config singleton
│   │   ├── routers/                HTTP route handlers
│   │   ├── providers/              MCP tool registration (@tool wrappers)
│   │   ├── services/               Business logic (generation, validation, …)
│   │   ├── schemas/                Pydantic request/response models
│   │   └── utils/                  Standalone CLI utilities (masking, aggregation)
│   ├── skills/                     MCP skill markdown files (served at skill://)
│   └── tests/
├── frontend/                       NLI Studio dashboard (Vite + React + TS)
│   └── src/
│       ├── pages/                  Route-level page components
│       ├── components/             Shared UI components
│       └── lib/                    API client helpers
├── docs/
│   ├── en/                         English guides (flow/, template/)
│   └── vi/                         Vietnamese guides (flow/, template/)
└── docker-compose.yml
```

## Local Start

Backend (port 8000):

```bash
cd backend
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Frontend (port 3000):

```bash
cd frontend
cp .env.example .env   # VITE_API_ENDPOINT=http://localhost:8000
npm install
npm run dev
```

Or run both with Docker Compose:

```bash
docker compose up --build
```

## Container Start

Both services via Compose (backend on 8000, frontend on 3000):

```bash
docker compose up --build
```

CI builds and pushes two images to Docker Hub:
`nli-synthetic-data-processing` (backend) and
`nli-synthetic-data-processing-frontend` (frontend).

Backend only:

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

The frontend's `VITE_API_ENDPOINT` is baked at build time (the bundle runs in the
browser). For local same-machine use the default `http://localhost:8000` works because
Compose publishes backend port 8000 to the host. For a remote deploy, rebuild the frontend
with `--build-arg VITE_API_ENDPOINT=https://your-backend-url`.

MCP endpoint:

```text
http://localhost:8000/mcp/
```

### Optional prompt refinement with MLflow

Start MLflow only when calibrating prompts:

```bash
cd backend
mkdir -p .mlflow/artifacts
uv run mlflow server \
  --backend-store-uri "sqlite:///$PWD/.mlflow/mlflow.db" \
  --default-artifact-root "file://$PWD/.mlflow/artifacts" \
  --host 127.0.0.1 \
  --port 5000
```

Open `http://127.0.0.1:5000`, then ask the agent to read
`skill://prompt_refinement`. The agent collects exactly three independent
verdict files and calls `evaluate_prompt_refinement`. Kappa below `0.85`
returns `needs_prompt_update`; the agent may then call
`propose_prompt_refinement_update` to get a user-facing manual prompt-update
proposal. Kappa at least `0.85` returns `accepted`. The backend does not register
prompt versions, promote aliases, lock prompts, or run another calibration automatically.

## Resources (MCP server: `nli-tools`)

| Resource | Purpose |
|----------|---------|
| `skill://instructor` | Start here: NLI task, resource map and phase flow |
| `skill://generator_plain` | Plain translation/naturalization for already-labeled NLI sources |
| `skill://generator_adversarial` | Controlled adversarial generation rules and self-checks |
| `skill://generator` | Legacy adversarial generator alias |
| `skill://delegation` | Stateless subagent prompt |
| `skill://progress_tracking` | Local audit, resume and cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric and verdict contract |
| `skill://prompt_refinement` | Optional three-model prompt calibration with MLflow |

## Phase Guides

| Area | Guide | Output |
|------|-------|--------|
| Project overview | [docs/en/project-overview.md](docs/en/project-overview.md) | `Architecture and runtime ownership` |
| Generator flow | [docs/en/flow/generator.md](docs/en/flow/generator.md) | `data/generated/*.csv` |
| Validator flow | [docs/en/flow/validator.md](docs/en/flow/validator.md) | `data/validated/*/validation_results.csv` |
| Progress tracking | [docs/en/flow/progress-tracking.md](docs/en/flow/progress-tracking.md) | `Runtime state and cleanup` |
| Generator template | [docs/en/template/generator.md](docs/en/template/generator.md) | `Harness prompt` |
| Validator template | [docs/en/template/validator.md](docs/en/template/validator.md) | `Harness prompt` |
| Post-validation template | [docs/en/template/post-validation.md](docs/en/template/post-validation.md) | `Consensus, PMI, paraphrase promotion, split prompt` |
| Prompt refinement template | [docs/en/template/prompt-refinement.md](docs/en/template/prompt-refinement.md) | `Main-agent/subagent orchestration prompt` |
