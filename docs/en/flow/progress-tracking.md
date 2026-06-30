# Progress Tracking

Progress state is local audit state for active runs. It is append-only and is
owned by MCP runtime tools.

## Runtime Paths

Paths are relative to the repository root. `data/` is a sibling of `backend/`,
not a child directory.

```text
.pipeline/runs/{run_id}/manifest.json
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/manifest.json
.pipeline/validation/runs/{run_id}/progress.jsonl
data/batches/{run_id}/
```

Batch CSV files under `data/batches/{run_id}` are runtime artifacts, not final
outputs.

## Event Lifecycle

```text
run.start
  -> claim
  -> row.done | row.skip
  -> batch.done
  -> ...
  -> merge.done
  -> run.end
  -> delete run state and data/batches/{run_id}
```

Validation uses validation-specific event names for start, merge, and end, but
the same claim, row, batch, verify, and cleanup model.

## Cleanup

Finalize deletes run state and `data/batches/{run_id}` only after merge and
verification succeed. Failed verification keeps both for debugging.

## Resume

If a process is interrupted while state still exists:

1. Call `list_generation_runs` or `list_validation_runs`.
2. Inspect progress with the corresponding progress tool.
3. Release abandoned active claims if needed.
4. Continue claiming and submitting batches.
