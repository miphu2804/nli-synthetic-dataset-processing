# Generator Prompt Template

Use this prompt when the Codex harness is already connected to MCP server
`nli-tools`.

```text
You are connected to MCP server `nli-tools`.

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
- get_run_progress
- release_batch_claim
- verify_progress_log
- finalize_generation_run
- list_generation_runs

Goal:
Generate Vietnamese NLI rows from this assigned sample range:
- input_path: <INPUT_CSV_OR_PARQUET>
- output_path: data/generated/<RUN_OR_DATASET_ID>.csv
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20
- generation_policy: <generator_plain_OR_generator_adversarial>

Flow:
1. Read MCP resources in this order:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://generator_plain or skill://generator_adversarial, matching
     generation_policy
2. Call start_generation_run with from_sample and to_sample.
3. Decide locally whether to use subagents or stay sequential.
4. Loop:
   - claim_next_batch
   - transform each claimed row according to the chosen generation policy
   - self-check label preservation, natural Vietnamese, and no cue leakage
   - submit_batch_result with rows and skipped_rows
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
- The harness decides if and how many subagents to spawn. Do not derive a
  worker count from backend rules.
- Only MCP runtime tools write progress.
- Subagents, if used, return JSON only and never call MCP tools.
- Batch CSV artifacts are runtime files under data/batches/{run_id}; finalize
  must clean them after successful verification.
```
