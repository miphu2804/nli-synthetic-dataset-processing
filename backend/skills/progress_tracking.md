# Progress Tracking - Local Audit and Resume

Progress state is local to one run:

```text
.pipeline/runs/{run_id}/
├── manifest.json
└── progress.jsonl

data/batches/{run_id}/
└── batch-00001.csv
```

The `.pipeline` directory exists only for audit and resume while the local run
is active. Batch CSV artifacts belong under `data/batches/{run_id}`. Do not push
local runtime artifacts to Git and do not share them between users.

## Ownership

The main agent is the only MCP caller. MCP runtime tools are the only progress
writers. Subagents never read or mutate progress state.

Use MCP tools instead of manually appending JSONL:

| Tool | Purpose |
|------|---------|
| `start_generation_run` | Create run manifest and `run.start` |
| `claim_next_batch` | Append `claim` and return the next batch |
| `submit_batch_result` | Write one batch and append row/batch events |
| `get_run_progress` | Read done, skipped, claimed and pending counts |
| `release_batch_claim` | Append `unclaim` for retry |
| `verify_progress_log` | Inspect integrity before manual debugging |
| `finalize_generation_run` | Merge, verify and remove successful local state |

## Event Flow

```text
run.start
  → claim
  → row.done | row.skip
  → batch.done
  → ...
  → merge.done
  → run.end
  → delete .pipeline/runs/{run_id} and data/batches/{run_id}
```

Events are plain JSONL records with `id`, `event`, `agent` and payload fields
such as `ts`, `batch_id`, `source_uid`, and `file`. Progress verification checks
duplicate done rows, done/skip overlap, missing batch files, and count
reconciliation.

`get_run_progress` rebuilds a snapshot from the log with `done_rows`,
`skipped_rows`, `claimed_rows`, `pending_rows`, `completed_batches`,
`failed_batches` and `active_claims`.

## Resume

If the process is interrupted while the container is still available:

1. Call `list_generation_runs`.
2. Call `get_run_progress(run_id)`.
3. Release an abandoned active claim if needed.
4. Continue claiming and submitting batches.

## Cleanup

`finalize_generation_run` deletes the run directory and `data/batches/{run_id}`
only after merge and verification succeed. Failed verification keeps those
runtime artifacts for debugging.
