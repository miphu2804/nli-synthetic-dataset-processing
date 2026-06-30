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
├── data/                           Runtime datasets and batch artifacts
├── docs/
│   ├── en/                         English guides (flow/, template/)
│   └── vi/                         Vietnamese guides (flow/, template/)
└── docker-compose.yml
```

## Local Start

Install backend dependencies once:

```bash
cd backend
uv sync
cd ..
```

Install `tmux` if it is not available:

```bash
# macOS
brew install tmux

# Debian/Ubuntu/WSL
sudo apt update && sudo apt install tmux

# Fedora
sudo dnf install tmux
```

On Windows, run these commands inside WSL. Native PowerShell does not provide
`tmux`.

Honcho is a backend runtime dependency. If
`uv --project backend run honcho --version` does not work, refresh the backend
environment:

```bash
cd backend
uv sync --dev
cd ..
```

### Manual tmux run

Use this when you want to run the two services separately. Keep both commands
inside the same `tmux` session so closing the terminal does not stop them.

```bash
tmux new -s nli-runtime
```

Inside that `tmux` session, start the backend API:

```bash
cd backend
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

In another `tmux` window, start MLflow:

```bash
# press Ctrl-b then c first
cd backend
uv run mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri sqlite:///$PWD/.mlflow/mlflow.db \
  --default-artifact-root file://$PWD/.mlflow/artifacts
```

Detach without stopping services: press `Ctrl-b`, then `d`.
Reconnect later:

```bash
tmux attach -t nli-runtime
```

Stop both services:

```bash
tmux kill-session -t nli-runtime
```

### Honcho tmux run

Run the backend and MLflow together from the repo root:

```bash
tmux new -s nli-runtime
```

Inside that `tmux` session, start Honcho:

```bash
uv --project backend run honcho start
```

Backend: `http://localhost:8000`
MCP endpoint: `http://localhost:8000/mcp/`
MLflow: `http://127.0.0.1:5000`

Detach with `Ctrl-b`, then `d`; reconnect with
`tmux attach -t nli-runtime`.

## Container Start

Backend via Compose (port 8000):

```bash
docker compose up --build
```

CI builds and pushes the backend image to Docker Hub:
`nli-synthetic-data-processing`.

Run the backend container with MCP, MLflow, and your host `Downloads` directory
available inside the container:

```bash
docker rm -f nli-tools 2>/dev/null || true

docker run -d --name nli-tools \
  --pull=always \
  -p 8000:8000 \
  -p 5000:5000 \
  -v "$HOME/Downloads:/downloads" \
  miphu2804/nli-synthetic-data-processing:latest
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

MLflow:

```text
http://localhost:5000
```

The container starts both FastAPI/FastMCP and MLflow with Honcho. Runtime state
is writable inside the container: generation/validation progress goes under
`.pipeline/`, batch CSV files under repo-root `data/batches/`, finalized
datasets under repo-root `data/generated/` or `data/validated/`, and MLflow
data under `.mlflow/`.
The published image starts MLflow on `0.0.0.0:5000` and allows browser access
through the published Docker port for local development.
Without a volume mount, those files are container-local and disappear when the
container is removed. Agents can still claim and submit batches through the MCP
endpoint as long as the input dataset path exists inside the container, for
example because it was created through the dataset write API or included in a
custom image.

For host files mounted from `Downloads`, use the container path:

```text
input_path=/downloads/data_normalize/dev_r1.csv
output_path=/downloads/data_normalize/generated/dev_r1_vie.csv
```

### Optional prompt refinement

Use prompt refinement before large-scale generation when the generator policy or
validator rubric needs calibration. In the connected agent workflow, the agent
already has the `nli-tools` MCP tools and skill lookup available. It loads
`prompt_refinement`, prepares one fixed calibration dataset, collects exactly
three independent verdict files, then calls `evaluate_prompt_refinement`.

Kappa below `0.85` returns `needs_prompt_update`; the main agent then reviews
the logged evidence such as `disagreement_rows.csv` and reports the smallest
evidence-backed next step for user approval. Kappa at least `0.85` returns
`accepted`. The backend logs the calibration evidence and does not propose
prompt edits, register prompt versions, promote aliases, lock prompts, or run
another calibration automatically.

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
| `skill://prompt_refinement` | Optional three-model prompt calibration with evidence logging |

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
