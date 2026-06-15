# Generator Prompt Template

Dùng prompt này khi Codex harness đã connect sẵn với MCP server
`nli-data-processing-mcp-server`.

```text
You are connected to MCP server `nli-data-processing-mcp-server`.

Available MCP resources:
- skill://instructor
- skill://execution
- skill://progress_tracking
- skill://generator
- skill://delegation
- skill://aggregator

Available generation tools:
- start_generation_run
- calculate_dispatch_plan
- claim_next_batch
- submit_batch_result
- get_run_progress
- release_batch_claim
- verify_progress_log
- finalize_generation_run
- list_generation_runs

Goal:
Generate Vietnamese adversarial NLI rows from this assigned sample range:
- input_path: <INPUT_CSV_OR_PARQUET>
- output_path: <DATA_GENERATED_OUTPUT_CSV>
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20

Flow:
1. Read MCP resources theo thứ tự:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://generator
2. Call start_generation_run with from_sample and to_sample.
3. Call calculate_dispatch_plan for the assigned sample count.
4. Loop:
   - claim_next_batch
   - transform each claimed row according to skill://generator
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
- Only MCP runtime tools write progress.
- Subagents, if used, return JSON only and never call MCP tools.
- Batch CSV artifacts are runtime files under data/batches/{run_id}; finalize
  must clean them after successful verification.
```
