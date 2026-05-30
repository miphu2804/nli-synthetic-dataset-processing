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

See `skills/` directory:

| Skill | What |
|-------|------|
| [`generator`](skills/generator.md) | NLI adversarial data generation guide (19 rules, 3-class, 3-tier) |
| [`generator-explanation-vi`](skills/generator-explanation-vi.md) | Vietnamese explanation of generator skill |

### How to use the generator

1. Read a chunk of data via `read_dataset_with_pandas` (batch_size=5-10)
2. Translate both premise + hypothesis to Vietnamese
3. Apply 1 adversarial transformation per row (pick rule matching original label)
4. Validate: label preserved, both Vietnamese, no artifact cues
5. Write chunk via `write_dataset_output`

Repeat until done. Use `get_skill("generator")` at any time to recall the full guide.

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
