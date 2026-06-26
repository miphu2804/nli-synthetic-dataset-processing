# Generator Flow

The generator phase creates Vietnamese NLI rows from a labeled source slice. The
harness reads one explicit generation policy, claims batches through MCP,
transforms rows, self-checks them, and submits only validated rows.

## Policy Selection

| Resource | Use when |
|----------|----------|
| `skill://generator_plain` | Source rows already contain a valid NLI/adversarial relation, such as ANLI-derived pairs. Translate and naturalize without adding a new adversarial transform. |
| `skill://generator_adversarial` | The goal is to create a new controlled adversarial Vietnamese NLI variant. Translate and apply one label-compatible rule. |
| `skill://generator` | Legacy adversarial alias for older harness prompts. Prefer an explicit policy for new runs. |

## State Machine

```text
START
  -> read skill://instructor
  -> read skill://execution
  -> read skill://progress_tracking
  -> choose and read skill://generator_plain or skill://generator_adversarial
  -> start_generation_run(from_sample, to_sample)
       creates .pipeline/runs/{run_id}
       creates data/batches/{run_id}
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
- Load exactly one generation policy for a run unless the user explicitly asks
  to compare policies.
- Do not generate hypothesis text with Python templates.
- Only MCP runtime tools write progress.
- Subagent fan-out is agent-owned. The backend does not compute or enforce a
  worker plan.
- Subagents may transform already-claimed rows but must return JSON only.
