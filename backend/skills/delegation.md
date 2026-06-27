# Delegation - Stateless Subagent Handoff

Use subagents only when the active user request or template asks for them.
Subagents are pure workers: they receive one claimed batch, return JSON and are
destroyed.

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

Send only the chosen generation policy and rows needed by that worker:

```text
You are a Vietnamese NLI generation worker.

Generation policy for this batch:
[include either generator_plain constraints or the assigned generator_adversarial rule definitions]

Constraints:
- Translate both premise and hypothesis to natural Vietnamese.
- For generator_plain, preserve the original relation without adding a new adversarial transform.
- For generator_adversarial, apply the assigned rule to hypothesis.
- Preserve the expected_label.
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

## Optional Handoff Flow

The connected main agent owns scheduling outside backend state. If subagents are
used:

1. Claim batches through `claim_next_batch`.
2. Send only already-claimed rows to workers.
3. Validate each returned JSON payload.
4. Call `submit_batch_result` for each resolved claim.
5. Retry failed rows up to 3 times, then submit them as skipped rows.
6. Continue until `claim_next_batch` returns complete, then call
   `finalize_generation_run`.
