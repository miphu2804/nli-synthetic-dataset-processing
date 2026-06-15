# NLI Synthetic Data Processing

Vietnamese README: [README.vi.md](README.vi.md)

## Local Start

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Container Start

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## Resources

| Resource | Purpose |
|----------|---------|
| `skill://instructor` | Start here: NLI task, resource map and phase flow |
| `skill://generator` | Transformation rules and generation self-checks |
| `skill://delegation` | Stateless parallel worker prompt |
| `skill://progress_tracking` | Local audit, resume and cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric and verdict contract |

## Phase Guides

| Area | Guide | Output |
|------|-------|--------|
| Project overview | [docs/en/project-overview.md](docs/en/project-overview.md) | `Architecture and runtime ownership` |
| Generator flow | [docs/en/flow/generator.md](docs/en/flow/generator.md) | `data/generated/*.csv` |
| Validator flow | [docs/en/flow/validator.md](docs/en/flow/validator.md) | `data/validated/*/validation_results.csv` |
| Progress tracking | [docs/en/flow/progress-tracking.md](docs/en/flow/progress-tracking.md) | `Runtime state and cleanup` |
| Generator template | [docs/en/template/generator.md](docs/en/template/generator.md) | `Harness prompt` |
| Validator template | [docs/en/template/validator.md](docs/en/template/validator.md) | `Harness prompt` |

