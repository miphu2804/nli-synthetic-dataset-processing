# NLI Synthetic Data Processing

Backend server (FastAPI + FastMCP) + agent skills for Vietnamese NLI adversarial data generation.

## Quick Start

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Method | Path | What |
|--------|------|------|
| GET | `/health` | Health check |
| POST | `/api/datasets/read` | Read batch from CSV/parquet |
| POST | `/api/datasets/write` | Write rows to CSV |
| GET | `/api/skills/` | List skills |
| GET | `/api/skills/{name}` | Get skill content |
| GET | `/mcp` | MCP endpoint (Streamable HTTP) |

## MCP Tools & Resources

| Tool | What |
|------|------|
| `read_dataset_with_pandas` | Read batch with offset + limit |
| `write_dataset_output` | Write rows to CSV |
| `get_skill` | Get skill by name |
| `list_skills` | List all skill names |

| Resource | What |
|----------|------|
| `skill://{name}` | Skill markdown content |

## REST Examples

```bash
# Read first 5 rows
curl -X POST http://127.0.0.1:8000/api/datasets/read \
  -H 'content-type: application/json' \
  -d '{"path":"data/anlitrain1.csv","batch_size":5,"batch_offset":0}'

# Write rows
curl -X POST http://127.0.0.1:8000/api/datasets/write \
  -H 'content-type: application/json' \
  -d '{"rows":[{"source_uid":"1","premise":"...","hypothesis":"...","label":"entailment"}],"output":{"format":"csv","path":"data/output.csv"}}'
```

## Skills

Agent guides in `skills/`:

| Skill | Purpose |
|-------|---------|
| [`generator`](skills/generator.md) | 19 adversarial rules, 3 labels, 3 tiers, anti-artifact constraints |
| [`progress_tracking`](skills/progress_tracking.md) | JSONL event log, per-agent hash chain, claim support |
| [`delegation`](skills/delegation.md) | Subagent handoff, parallel execution, multi-agent collaboration |
| [`execution`](skills/execution.md) | What runs where: LLM for text, bash for queries, Monty for untrusted code |

Vietnamese docs in [`docs/`](docs/):

| Doc | What |
|-----|------|
| [`project-overview-vi`](docs/project-overview-vi.md) | Tổng quan |
| [`generator-explanation-vi`](docs/generator-explanation-vi.md) | Giải thích generator |
| [`progress-tracking-vi`](docs/progress-tracking-vi.md) | Giải thích progress tracking |
| [`delegation-vi`](docs/delegation-vi.md) | Giải thích delegation |

## Workflow

```
1. Agent loads skills via get_skill
2. Read dataset via read_dataset_with_pandas (batch_size=5-10)
3. Claim rows in progress.jsonl
4. Spawn subagent to translate + transform each batch
5. Validate, write CSV, append progress.jsonl
6. Loop until done, merge part files
```

## Project Structure

```
src/
├── main.py
├── app_config.py
├── services/          # reader, writer, skill
├── schemas/           # request/response models
└── routers/           # REST endpoints
skills/                # Agent skill guides
docs/                  # Vietnamese documentation
data/                  # Dataset I/O
.pipeline/             # Runtime: progress.jsonl + outputs
```
