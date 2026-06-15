# NLI Synthetic Data Processing

Vietnamese NLI adversarial data generation using 19 label-compatible
transformations. An LLM harness connects through MCP, processes assigned sample
ranges, and writes verified CSV outputs.

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

Use these docs when the Codex harness is already connected to the MCP server.

| Area | Guide | Output |
|------|-------|--------|
| Project overview | [docs/en/project-overview.md](docs/en/project-overview.md) | `Architecture and runtime ownership` |
| Generator flow | [docs/en/flow/generator.md](docs/en/flow/generator.md) | `data/generated/*.csv` |
| Validator flow | [docs/en/flow/validator.md](docs/en/flow/validator.md) | `data/validated/*/validation_results.csv` |
| Progress tracking | [docs/en/flow/progress-tracking.md](docs/en/flow/progress-tracking.md) | Runtime state and cleanup |
| Generator template | [docs/en/template/generator.md](docs/en/template/generator.md) | Codex harness prompt |
| Validator template | [docs/en/template/validator.md](docs/en/template/validator.md) | Codex harness prompt |

The MCP start tools use 1-based inclusive sample ranges:

```text
from_sample=1, to_sample=20  -> first 20 rows
from_sample=21, to_sample=40 -> next 20 rows
```

## Runtime State

Progress is an append-only JSONL event log at:

```text
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/progress.jsonl
```

Batch CSV artifacts live under:

```text
data/batches/{run_id}
```

MCP runtime tools are the only progress writers. The main agent calls those
tools sequentially. Subagents receive claimed rows, transform text, and return
JSON only.

Finalize succeeds only after merge and verification. On success it cleans local
run state and `data/batches/{run_id}`. Failed verification keeps those runtime
artifacts for debugging.
