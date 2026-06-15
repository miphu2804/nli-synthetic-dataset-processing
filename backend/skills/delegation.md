# Delegation - Stateless Subagent Handoff

Use subagents only when processing at least 100 assigned rows. Subagents are
pure workers: they receive one batch, return JSON and are destroyed.

## Ownership

| Main agent | Subagent |
|------------|----------|
| Calls MCP runtime tools | Never calls MCP |
| Claims batches sequentially | Receives already-claimed rows |
| Assigns one rule per row | Applies the assigned rule |
| Validates returned rows | Self-checks output |
| Submits batches and updates progress | Never reads or writes progress |
| Finalizes the run | Has no run awareness |

MCP runtime tools are the only progress writers. Parallelism happens during
text transformation, not during progress mutation.

## Worker Prompt Template

Send only the assigned rules and rows needed by that worker:

```text
You are a Vietnamese NLI adversarial transformer.

Rules assigned in this batch:
[include only assigned rule definitions]

Constraints:
- Translate both premise and hypothesis to natural Vietnamese.
- Apply the assigned rule to hypothesis.
- Preserve the original label.
- Avoid unnecessary label-leaking cue words.
- Return JSON only.

Rows:
[
  {
    "source_uid": "...",
    "premise": "...",
    "hypothesis": "...",
    "label": "...",
    "rule": "..."
  }
]

Return:
[
  {
    "source_uid": "...",
    "premise": "... Vietnamese ...",
    "hypothesis": "... Vietnamese transformed ...",
    "label": "... unchanged ..."
  }
]
```

## Parallel Flow

Calculate the pool before claiming:

```text
total_batches = ceil(samples / batch_size)
parallel_workers = min(total_batches, max_parallel_workers)
```

1. Call `calculate_dispatch_plan(samples=total_target_rows, batch_size=batch_size)`.
2. Claim `parallel_workers` different batches by calling `claim_next_batch`
   sequentially.
3. Spawn all claimed batches in parallel immediately.
4. As each worker returns, validate and call `submit_batch_result`.
5. Claim and dispatch one replacement batch immediately to refill the free slot.
6. Failed rows are retried up to 3 times, then submitted as skipped rows.
7. After all claims resolve, call `finalize_generation_run`.

Keep the sliding window full. Do not scale gradually from 3 workers.
