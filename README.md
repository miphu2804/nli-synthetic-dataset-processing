# NLI Synthetic Data Processing

Vietnamese NLI adversarial data generation using 19 rule-based transformations across 3 difficulty tiers, driven by agent skills.

## Quick Start

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Project Structure

```
skills/                     # Agent skill definitions
├── generator.md            # 19-rule NLI pipeline (entailment/neutral/contradiction)
├── progress_tracking.md    # JSONL append-only event log + per-agent hash chain
├── delegation.md           # Subagent parallel execution + responsibility split
├── execution.md            # Runtime boundary: LLM / Bash / Monty sandbox
└── aggregator.md           # CSV merge + dedup

src/                        # FastAPI backend
├── main.py                 # App entry point
├── app_config.py           # Env vars
├── routers/                # REST endpoints
├── schemas/                # Request/response models
└── services/               # reader, writer, skill loader

.pipeline/                  # Runtime state (git tracked)
└── progress.jsonl          # Append-only event log

data/
├── original/               # Raw input datasets
├── generated/              # Final output CSVs
├── batches/                # Temp chunks (cleaned after merge)
└── processed/              # Archived processed datasets

docs/                       # Vietnamese documentation
```

## Skills

| Skill | Purpose |
|-------|---------|
| [`generator`](skills/generator.md) | 19 adversarial rules × 3 labels × 3 tiers, anti-artifact constraints, output schema |
| [`progress_tracking`](skills/progress_tracking.md) | JSONL event log, per-agent hash chain, claim/resume/verify |
| [`delegation`](skills/delegation.md) | Subagent handoff, parallel execution |
| [`execution`](skills/execution.md) | LLM → text, Bash → I/O, Monty sandbox → Python |
| [`aggregator`](skills/aggregator.md) | Merge & deduplicate CSV files |

## Output Schema

```csv
source_uid, premise, hypothesis, label
```

| Column | Description |
|--------|-------------|
| `source_uid` | Original row ID from input |
| `premise` | Translated to Vietnamese |
| `hypothesis` | Translated + adversarially transformed (Vietnamese) |
| `label` | `entailment` / `neutral` / `contradiction` (preserved from input) |

## State Machine

```
  START ──→ load skills ──→ read dataset ──→ init .pipeline/progress.jsonl
                                                    │
                    ┌───────────────────────────────┘
                    ▼
              ┌──────────┐
         ┌───→│  CLAIM   │  claim next N rows (prevents duplicate work)
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ TRANSFORM│  subagent: translate EN→VI + apply adversarial rule
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ VALIDATE │  label preserved? VI? grammar? no cue leak?
         │    └──┬───┬───┘
         │   PASS│   │FAIL → retry (max 3) → skip + log reason
         │       ▼
         │    ┌──────────┐
         │    │  WRITE   │  write part{N}.csv + append row.done to log
         │    └────┬─────┘
         │         ▼
         │    ┌──────────┐
         │    │ MORE?    │──YES──┘
         │    └────┬─────┘
         │         │NO
         │         ▼
         │    ┌──────────┐
         └────│  MERGE   │  merge part*.csv → final, rm part*, verify chain
              └──────────┘
```

## Progress Tracking

Append-only JSONL at `.pipeline/progress.jsonl`. Each agent has its own hash chain — two agents writing concurrently won't collide. `claim` prevents duplicate work.

```jsonl
{"id":"main-0","ts":"...","event":"run.start","agent":"main","prev_hash":"0","total":100}
{"id":"main-1","ts":"...","event":"claim","agent":"main","prev_hash":"abc...","rows":"1-100"}
{"id":"main-2","ts":"...","event":"row.done","agent":"main","prev_hash":"def...","source_uid":1}
{"id":"main-3","ts":"...","event":"batch.done","agent":"main","prev_hash":"ghi...","batch":1,"rows":"1-10"}
{"id":"main-4","ts":"...","event":"run.end","agent":"main","prev_hash":"jkl...","processed":100,"skipped":0}
```

