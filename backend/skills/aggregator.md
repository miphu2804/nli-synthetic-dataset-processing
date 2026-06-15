# Aggregator - Finalize Local Run

Use the MCP tool:

```text
finalize_generation_run(run_id)
```

The server:

1. Rejects finalize while claims or pending rows remain.
2. Merges local batch CSV files from `data/batches/{run_id}` into the requested
   output path.
3. Appends `merge.done` and `run.end`.
4. Verifies progress integrity and final output row count.
5. Deletes `.pipeline/runs/{run_id}` and `data/batches/{run_id}` after
   successful verification.

If verification fails, the run directory and batch CSVs remain available for
investigation.
