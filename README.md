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
| `skill://generator` | Transformation rules and MCP workflow |
| `skill://delegation` | Stateless parallel worker prompt |
| `skill://progress_tracking` | Local audit, resume and cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |

## Container Start

```bash
docker run --rm -p 8000:8000 IMAGE:<tag>
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## MCP Flow

```text
start_generation_run
  → calculate_dispatch_plan(samples=total_target_rows, batch_size=batch_size)
  → claim enough batches to fill parallel_workers slots
  → dispatch claimed batches to LLM subagents in parallel
  → submit each completed batch and refill its slot immediately
  → repeat until claim_next_batch returns complete
  → finalize_generation_run
```

## State Machine

```text
  START → load skills → start run → init .pipeline/runs/{run_id}
                                      │
                    ┌─────────────────┘
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
         │    │   WRITE   │  batch CSV + row.done | row.skip + batch.done
         │    └─────┬─────┘
         │          ▼
         │    ┌───────────┐
         └────│   MORE?   │── YES
              └─────┬─────┘
                    │ NO
                    ▼
              ┌───────────┐
              │ FINALIZE  │  merge output → verify → cleanup local run
              └───────────┘
```

## Progress Tracking

Progress is an append-only JSONL event log at
`.pipeline/runs/{run_id}/progress.jsonl`. MCP runtime tools are the only progress
writers. The main agent calls those tools sequentially. Subagents receive
claimed rows, transform text and return JSON only.

The server appends:

```text
run.start
  → claim
  → row.done | row.skip
  → batch.done
  → ...
  → merge.done
  → run.end
  → delete .pipeline/runs/{run_id}
```

Each event includes `id`, `ts`, `event`, `agent` and `prev_hash`. Do not edit,
share or push `.pipeline`.

```jsonl
{"id":"main-1","event":"claim","agent":"main","prev_hash":"abc...","ts":"...","batch_id":"batch-00001","source_uids":[1,2],"row_count":2}
```

If interrupted, call `list_generation_runs`, inspect with `get_run_progress`
and release abandoned claims with `release_batch_claim`.
