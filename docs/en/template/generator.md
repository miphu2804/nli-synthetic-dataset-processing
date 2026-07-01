# Generator Prompt Template

Use this prompt when the Codex harness is already connected to MCP server
`nli-tools`. Replace every placeholder with the values for the current run.

```text
You are main agent connected to MCP server `nli-tools`.

Available MCP resources:
- skill://instructor
- skill://execution
- skill://progress_tracking
- skill://generator_plain
- skill://generator_adversarial
- skill://generator
- skill://delegation
- skill://aggregator

Available generation tools:
- start_generation_run
- claim_next_batch
- submit_batch_result
- submit_batch_result_from_artifacts
- get_run_progress
- release_batch_claim
- verify_progress_log
- finalize_generation_run
- list_generation_runs

SPAWN <SUBAGENT_COUNT> sub agents for data generation using
<MODEL_NAME_AND_REASONING_LEVEL>

Goal:
Generate Vietnamese NLI rows from this assigned sample range:
- input_path: "<INPUT_CSV_OR_PARQUET>"
- output_path: "<OUTPUT_CSV_PATH such as data/generated/<RUN_OR_DATASET_ID>.csv>"
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE_OR_END>
- batch_size: <BATCH_SIZE>
- generation_policy: <generator_plain.md_OR_generator_adversarial.md>

Flow:
1. Read MCP resources in this order:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://generator_plain or skill://generator_adversarial, matching
     generation_policy
2. Call start_generation_run with from_sample and to_sample.
3. Use subagents only if the active user request or template asks for them.
4. Loop:
   - claim_next_batch
   - create a fresh worker for that claimed batch only when using subagents
   - transform each claimed row according to the chosen generation policy
   - if using subagents, pass only the claimed rows plus batch.artifact_targets
   - if using subagents, have the worker write rows_csv_path and optional skipped_rows_csv_path, then return only a tiny JSON ack
   - self-check label preservation, natural Vietnamese, and no cue leakage
   - if using subagents, call submit_batch_result_from_artifacts
   - otherwise call submit_batch_result with rows and skipped_rows
   - continue until claim_next_batch returns complete
5. Call verify_progress_log.
6. Read skill://aggregator.
7. Call finalize_generation_run.
8. Report run_id, output_path, rows_written, skipped rows, and unresolved issues.

Rules:
- Use MCP resource reads for the listed `skill://...` resources before calling
  generation tools.
- Use `generator_plain` for ANLI-derived or already-adversarial NLI source rows.
- Use `generator_adversarial` only when creating a new controlled adversarial
  variant is the explicit goal.
- If subagents are explicitly requested, the connected harness owns scheduling
  outside backend state.
- Subagents must be visible Codex workers in the active Desktop session, not
  `codex exec`, `claude -p`, subprocesses, or local worker scripts.
- Use at most one claimed batch per worker context. Do not reuse the same
  worker for multiple generation batches, because prior rows and checks can
  leak into later batch decisions.
- Only MCP runtime tools write progress.
- Subagents, if used, write worker CSV artifacts to the claimed batch paths,
  return only a tiny JSON ack, and never call MCP tools.
- Do not paste a full batch payload back into chat when artifact submission is
  available.
- Do not create or run local orchestration scripts, thin drivers, subprocess
  workers, `fastmcp.Client` loops, `codex exec`, or `claude -p` to process
  generation batches. If visible Codex subagents are unavailable or too slow,
  stop and report the blocker instead of switching execution mode.
- Keep the requested batch_size unchanged unless the user explicitly approves a
  different value.
```
