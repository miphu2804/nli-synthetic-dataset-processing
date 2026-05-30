# NLI Synthetic Data Processing

Backend server exposing dataset I/O as MCP tools + REST endpoints, plus a generator skill for Vietnamese NLI adversarial data.

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
| GET | `/api/skills/` | List available skills |
| GET | `/api/skills/{name}` | Get skill content (markdown) |
| GET | `/mcp` | MCP server (Streamable HTTP) |

### MCP Tools

| Tool | What |
|------|------|
| `read_dataset_with_pandas` | Read dataset with batch offset + limit |
| `write_dataset_output` | Write rows to CSV file |
| `get_skill` | Get skill guide by name |
| `list_skills` | List all skill names |

### MCP Resources

| URI | What |
|-----|------|
| `skill://{name}` | Skill markdown content |

## REST Examples

Read first 5 rows:

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/read \
  -H 'content-type: application/json' \
  -d '{"path":"data/anlitrain1.csv","batch_size":5,"batch_offset":0}'
```

Write rows:

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/write \
  -H 'content-type: application/json' \
  -d '{
    "rows":[
      {"source_uid":"1","premise":"...","hypothesis":"...","label":"entailment"}
    ],
    "output":{"format":"csv","path":"data/output.csv"}
  }'
```

## Skills

Agent skills in `skills/` (Markdown guides loaded via `get_skill`):

| Skill | What |
|-------|------|
| [`generator`](skills/generator.md) | NLI adversarial rules (19 rules, 3 labels, 3 tiers) |
| [`progress_tracking`](skills/progress_tracking.md) | JSONL event log with hash chain |
| [`delegation`](skills/delegation.md) | Subagent orchestration & parallel execution |

Vietnamese docs in `docs/`:

| Doc | What |
|-----|------|
| [`project-overview-vi`](docs/project-overview-vi.md) | Tổng quan dự án |
| [`generator-explanation-vi`](docs/generator-explanation-vi.md) | Giải thích generator skill |
| [`progress-tracking-vi`](docs/progress-tracking-vi.md) | Giải thích progress tracking |
| [`delegation-vi`](docs/delegation-vi.md) | Giải thích delegation |

### How to use the generator

1. Agent loads 3 skills: `get_skill("generator")` → references `progress_tracking` + `delegation`
2. Read chunk via `read_dataset_with_pandas` (batch_size=5-10)
3. Spawn subagent to translate + transform each batch (see delegation skill)
4. Validate output, write CSV, append `progress.jsonl`
5. Loop until done

## Project Structure

```
src/
├── main.py              # FastAPI app + FastMCP mount
├── app_config.py        # Env config (OPENAI_API_KEY, etc.)
├── prompt_template.py   # Prompt constants
├── services/
│   ├── dataset_reader_service.py
│   ├── dataset_writer_service.py
│   └── skill_service.py
├── schemas/
│   ├── dataset_reader_schema.py
│   ├── dataset_writer_schema.py
│   └── dataset_generate_schema.py
└── routers/
    ├── reader_router.py
    ├── writer_router.py
    └── skill_router.py
skills/
├── generator.md
└── generator-explanation-vi.md
data/
└── anlitrain1.csv       # Example input (ANLI train set)
```
