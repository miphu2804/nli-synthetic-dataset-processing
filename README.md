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

## State Machine

```
  START ──→ get_skill × 3 ──→ read_dataset ──→ init progress.jsonl
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
              ┌──────────┐
         ┌───→│  CLAIM   │  grep progress.jsonl → claim next N rows
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ TRANSFORM│  subagent: translate VI + adversarial rule
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ VALIDATE │  label? VI? grammar? rule applied?
         │    └──┬───┬───┘
         │   PASS│   │FAIL → retry / skip
         │       ▼
         │    ┌──────────┐
         │    │  WRITE   │  write_dataset + append row.done to log
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ MORE?    │──YES──┘
         │    └────┬─────┘
         │         │NO
         │         ▼
         │    ┌──────────┐
         └────│  MERGE   │  merge part*.csv → verify hash chain
              └──────────┘
```

## Sample progress.jsonl (2 agents)

```jsonl
{"event":"run.start","agent":"alice","prev_hash":"0"}
{"event":"claim","agent":"alice","rows":"1-5","prev_hash":"abc..."}
{"event":"row.done","agent":"alice","source_uid":1,"prev_hash":"def..."}
{"event":"row.done","agent":"alice","source_uid":2,"prev_hash":"ghi..."}
{"event":"batch.done","agent":"alice","batch":1,"prev_hash":"jkl..."}
                                    ← bob's chain starts here, no conflict
{"event":"run.start","agent":"bob","prev_hash":"0"}
{"event":"claim","agent":"bob","rows":"6-10","prev_hash":"mno..."}
{"event":"row.skip","agent":"alice","source_uid":12,"reason":"premise empty"}
{"event":"row.done","agent":"bob","source_uid":6,"prev_hash":"pqr..."}
{"event":"run.end","agent":"alice","processed":50,"prev_hash":"stu..."}
```

Each agent has its own hash chain. Alice and Bob append simultaneously — chains don't collide. `claim` prevents duplicate work.

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
