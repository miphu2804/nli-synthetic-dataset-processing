# Validator Prompt Template

Dùng prompt này khi Codex harness đã connect sẵn với MCP server
`nli-data-processing-mcp-server`.

```text
You are connected to MCP server `nli-data-processing-mcp-server`.

Available MCP resources:
- skill://validator

Available validation tools:
- start_validation_run
- claim_next_validation_batch
- submit_validation_result
- get_validation_progress
- release_validation_batch_claim
- verify_validation_progress_log
- finalize_validation_run
- list_validation_runs

Goal:
Validate generated Vietnamese NLI rows through masked labels:
- input_path: <GENERATED_CSV_WITH_HIDDEN_LABELS>
- output_dir: <DATA_VALIDATED_OUTPUT_DIR>
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20

Flow:
1. Read skill://validator.
2. Call start_validation_run with from_sample and to_sample.
3. Loop:
   - claim_next_validation_batch
   - assign predicted_label from premise and hypothesis only
   - submit_validation_result with one verdict per claimed source_uid
   - continue until claim_next_validation_batch returns complete
4. Call verify_validation_progress_log.
5. Call finalize_validation_run.
6. Report run_id, output_path, total_rows, accepted_rows, rejected_rows, and
   unresolved issues.

Rules:
- Claimed rows expose only source_uid, premise, hypothesis, and masked_label.
- Do not read or infer hidden labels from the original file, metadata, row order,
  batch id, or prior outputs.
- If labels are numeric in the run, return the exact numeric label id.
- Finalize writes validation_results.csv and cleans both .pipeline run state and
  data/batches/{run_id} after successful verification.
```

## State Machine

```text
START
  -> đọc skill://validator
  -> start_validation_run(from_sample, to_sample)
       tạo .pipeline/validation/runs/{run_id}
       tạo data/batches/{run_id}
  -> claim_next_validation_batch
       trả về source_uid, premise, hypothesis, masked_label
  -> predict labels mà không đọc hidden labels
  -> submit_validation_result
       runtime trusted ghi accepted/rejected comparison vào batch CSV
  -> claim_next_validation_batch
       claimed  -> lặp lại predict và submit
       waiting  -> inspect active claims hoặc release abandoned claim
       complete -> verify_validation_progress_log
  -> finalize_validation_run
       success -> validation_results.csv tồn tại
               -> .pipeline/validation/runs/{run_id} bị xóa
               -> data/batches/{run_id} bị xóa
       failure -> runtime artifacts được giữ để debug
```
