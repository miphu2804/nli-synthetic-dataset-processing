# Generator Flow

The generator phase creates Vietnamese adversarial NLI rows from a labeled
source slice. The harness reads the generation resources, claims batches through
MCP, transforms rows, self-checks them, and submits only validated rows.

## State Machine

```text
START
  -> read skill://instructor
  -> read skill://execution
  -> read skill://progress_tracking
  -> read skill://generator
  -> start_generation_run(from_sample, to_sample)
       creates .pipeline/runs/{run_id}
       creates data/batches/{run_id}
  -> calculate_dispatch_plan
  -> claim_next_batch
  -> transform claimed rows
  -> self-check generated rows
       pass -> submit_batch_result
       fail -> retry or submit skipped_rows
  -> claim_next_batch
       claimed  -> repeat transform and submit
       waiting  -> inspect active claims or release abandoned claim
       complete -> verify_progress_log
  -> read skill://aggregator
  -> finalize_generation_run
       success -> data/generated output exists
               -> .pipeline/runs/{run_id} removed
               -> data/batches/{run_id} removed
       failure -> runtime artifacts remain for debugging
```

## Output Schema

```csv
source_uid,premise,hypothesis,label
```

## Notes

- Use `from_sample` and `to_sample` as one-based inclusive sample numbers.
- Preserve the source label.
- Do not generate hypothesis text with Python templates.
- Only MCP runtime tools write progress.
- Subagents may transform already-claimed rows but must return JSON only.
