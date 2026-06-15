# NLI Synthetic Data Processing

Vietnamese NLI adversarial data generation using 19 label-compatible
transformations. An LLM harness connects through MCP, processes one local slice
and writes one output CSV.

## Local Start

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Skills

| Resource | Purpose |
|----------|---------|
| `skill://instructor` | Start here: NLI task, resource map and phase flow |
| `skill://generator` | Transformation rules and generation self-checks |
| `skill://delegation` | Stateless parallel worker prompt |
| `skill://progress_tracking` | Local audit, resume and cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric and verdict contract |

Offline validation guide: `docs/validation-flow.md`

## Container Start

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## State Machine

```text
  START → load instructor → start run → init .pipeline/runs/{run_id}
                                      + data/batches/{run_id}
                                          │
                    ┌─────────────────────┘
                    ▼
              ┌───────────┐
         ┌───→│   CLAIM   │  claim next local batch
         │    └─────┬─────┘
         │          ▼
         │    ┌───────────┐
         │    │ TRANSFORM │  subagent: translate EN → VI + apply adversarial rule
         │    └─────┬─────┘
         │          ▼
         │    ┌───────────┐
         │    │ VALIDATE  │  label preserved? natural VI? no cue leak?
         │    └──┬────┬───┘
         │  PASS │    │ FAIL → retry (max 3) → row.skip + reason
         │       ▼
         │    ┌───────────┐
         │    │   WRITE   │  data/batches CSV + row.done | row.skip + batch.done
         │    └─────┬─────┘
         │          ▼
         │    ┌───────────┐
         └────│   MORE?   │── YES
              └─────┬─────┘
                    │ NO
                    ▼
              ┌───────────┐
              │ FINALIZE  │  merge output → verify → cleanup state + batches
              └───────────┘
```

## Progress Tracking

Progress is an append-only JSONL event log at
`.pipeline/runs/{run_id}/progress.jsonl`. Batch CSV artifacts live under
`data/batches/{run_id}`. MCP runtime tools are the only progress writers. The
main agent calls those tools sequentially. Subagents receive claimed rows,
transform text and return JSON only.


```jsonl
{"id":"main-1","event":"claim","agent":"main","prev_hash":"abc...","ts":"...","batch_id":"batch-00001","source_uids":[1,2],"row_count":2}
```
