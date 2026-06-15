# NLI Synthetic Data Processing

English README mặc định: [README.md](README.md)

## Chạy Local

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Chạy Container

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## Kĩ năng

| Kĩ năng | Mục đích |
|----------|----------|
| `skill://instructor` | Đọc đầu tiên để hiểu NLI task, resource map và phase flow |
| `skill://generator` | Transformation rules và generation self-checks |
| `skill://delegation` | Prompt cho stateless parallel worker |
| `skill://progress_tracking` | Local audit, resume và cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric và verdict contract |

## Tài liệu hướng dẫn

| Phạm vi | Tài liệu | Kết quả |
|------|-------|--------|
| Project overview | [docs/vi/project-overview.md](docs/vi/project-overview.md) | `Architecture and runtime ownership` |
| Generator flow | [docs/vi/flow/generator.md](docs/vi/flow/generator.md) | `data/generated/*.csv` |
| Validator flow | [docs/vi/flow/validator.md](docs/vi/flow/validator.md) | `data/validated/*/validation_results.csv` |
| Progress tracking | [docs/vi/flow/progress-tracking.md](docs/vi/flow/progress-tracking.md) | `Runtime state and cleanup` |
| Generator template | [docs/vi/template/generator.md](docs/vi/template/generator.md) | `Harness prompt` |
| Validator template | [docs/vi/template/validator.md](docs/vi/template/validator.md) | `Harness prompt` |
