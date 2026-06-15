# NLI Synthetic Data Processing

English README: [README.md](README.md)

Cấu trúc monorepo:

```text
nli-synthetic-data-processing/
├── backend/                        FastAPI + FastMCP server (Python, uv)
│   ├── src/
│   │   ├── main.py                 Entry point — kết nối FastAPI + FastMCP
│   │   ├── app_config.py           Config singleton (pydantic-settings)
│   │   ├── routers/                HTTP route handlers
│   │   ├── providers/              Đăng ký MCP tool (@tool wrappers)
│   │   ├── services/               Business logic (generation, validation, …)
│   │   ├── schemas/                Pydantic request/response models
│   │   └── utils/                  CLI utilities (masking, aggregation)
│   ├── skills/                     Skill markdown files (phục vụ tại skill://)
│   └── tests/
├── frontend/                       NLI Studio dashboard (Vite + React + TS)
│   └── src/
│       ├── pages/                  Các trang theo route
│       ├── components/             UI components dùng chung
│       └── lib/                    API client helpers
├── docs/
│   ├── en/                         Tài liệu tiếng Anh (flow/, template/)
│   └── vi/                         Tài liệu tiếng Việt (flow/, template/)
└── docker-compose.yml
```

## Chạy Local

Backend (cổng 8000):

```bash
cd backend
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Frontend (cổng 3000):

```bash
cd frontend
cp .env.example .env   # VITE_API_ENDPOINT=http://localhost:8000
npm install
npm run dev
```

Hoặc chạy cả hai bằng Docker Compose:

```bash
docker compose up --build
```

## Chạy Container

Cả hai service qua Compose (backend port 8000, frontend port 3000):

```bash
docker compose up --build
```

CI tự động build và push hai image lên Docker Hub:
`nli-synthetic-data-processing` (backend) và
`nli-synthetic-data-processing-frontend` (frontend).

Chỉ backend:

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

`VITE_API_ENDPOINT` của frontend được bake tại build time (bundle chạy trên browser).
Với local cùng máy, mặc định `http://localhost:8000` hoạt động vì Compose publish port 8000 ra host.
Với remote deploy, rebuild frontend với `--build-arg VITE_API_ENDPOINT=https://your-backend-url`.

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## Kĩ năng (MCP server: `nli-tools`)

| Kĩ năng | Mục đích |
|----------|----------|
| `skill://instructor` | Đọc đầu tiên: NLI task, resource map và phase flow |
| `skill://generator` | Transformation rules và generation self-checks |
| `skill://delegation` | Prompt cho stateless parallel worker |
| `skill://progress_tracking` | Local audit, resume và cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric và verdict contract |

## Tài liệu hướng dẫn

| Phạm vi | Tài liệu | Kết quả |
|---------|---------|---------|
| Project overview | [docs/vi/project-overview.md](docs/vi/project-overview.md) | `Architecture and runtime ownership` |
| Generator flow | [docs/vi/flow/generator.md](docs/vi/flow/generator.md) | `data/generated/*.csv` |
| Validator flow | [docs/vi/flow/validator.md](docs/vi/flow/validator.md) | `data/validated/*/validation_results.csv` |
| Progress tracking | [docs/vi/flow/progress-tracking.md](docs/vi/flow/progress-tracking.md) | `Runtime state and cleanup` |
| Generator template | [docs/vi/template/generator.md](docs/vi/template/generator.md) | `Harness prompt` |
| Validator template | [docs/vi/template/validator.md](docs/vi/template/validator.md) | `Harness prompt` |
