# Delegation - Stateless Subagent Handoff

Use subagents only when the active user request or template asks for them.
Subagents are pure workers: they receive one claimed batch, write worker CSV
artifacts, return a tiny JSON ack, and are destroyed.

Create a fresh worker context for each claimed batch. Do not reuse one worker
for multiple batches unless the user explicitly accepts the context-leakage
risk and changes the execution mode.

In Codex Desktop, "subagent" means a visible Codex worker in the active session.
Do not replace it with `codex exec`, `claude -p`, subprocess workers, a local
orchestrator script, or a headless `fastmcp.Client` loop unless the user
explicitly approves headless execution.

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

Keep the requested `batch_size` unchanged. If visible subagents are unavailable,
the batch payload is too large for the active tool response, or workers are too
slow, stop and report the blocker instead of silently changing batch size or
switching to local scripts.

Shell commands may be used only for lightweight inspection/debugging, such as
`rg`, `sed`, `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, and read-only
progress checks. Do not use Bash/Python scripts to claim, transform, submit, or
finalize runtime batches.

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
- Write the finished rows to rows_csv_path.
- If any row is skipped, write skipped_rows_csv_path.
- Return only a tiny JSON ack.

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

Artifact targets:
{
  "rows_csv_path": ".../batch-00001.rows.csv",
  "skipped_rows_csv_path": ".../batch-00001.skips.csv"
}

Return:
{
  "rows_csv_path": ".../batch-00001.rows.csv",
  "rows_count": 20,
  "skipped_rows_csv_path": ".../batch-00001.skips.csv",
  "skipped_count": 0
}
```

## Optional Handoff Flow

The connected main agent owns scheduling outside backend state. If subagents are
used:

1. Claim batches through `claim_next_batch`.
2. Send only one already-claimed batch to each fresh worker.
3. Validate each returned tiny JSON ack and the written worker CSV artifacts.
4. Call `submit_batch_result_from_artifacts` for each resolved claim.
5. Retry failed rows up to 3 times, then submit them as skipped rows.
6. Continue until `claim_next_batch` returns complete, then call
   `finalize_generation_run`.
