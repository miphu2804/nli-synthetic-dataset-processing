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
1. Read skill://instructor, skill://execution, skill://progress_tracking, and
   skill://generator.
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
- Only MCP runtime tools write progress.
- Subagents, if used, return JSON only and never call MCP tools.
- Batch CSV artifacts are runtime files under data/batches/{run_id}; finalize
  must clean them after successful verification.
```

## State Machine

```text
START
  -> đọc skill://instructor
  -> đọc skill://execution
  -> đọc skill://progress_tracking
  -> đọc skill://generator
  -> start_generation_run(from_sample, to_sample)
       tạo .pipeline/runs/{run_id}
       tạo data/batches/{run_id}
  -> calculate_dispatch_plan
  -> claim_next_batch
  -> transform claimed rows
  -> self-check generated rows
       pass -> submit_batch_result
       fail -> retry hoặc submit skipped_rows
  -> claim_next_batch
       claimed  -> lặp lại transform và submit
       waiting  -> inspect active claims hoặc release abandoned claim
       complete -> verify_progress_log
  -> đọc skill://aggregator
  -> finalize_generation_run
       success -> data/generated output tồn tại
               -> .pipeline/runs/{run_id} bị xóa
               -> data/batches/{run_id} bị xóa
       failure -> runtime artifacts được giữ để debug
```

## Ghi chú

Dataset gốc cần có `premise`, `hypothesis`, `label`. Generator phải giữ nguyên
label gốc, tạo tiếng Việt tự nhiên, và không để lộ cue làm label quá dễ đoán.
