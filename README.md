# NLI Synthetic Data Processing

## Quick Start

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
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
└── data.csv       # Example input 
```
