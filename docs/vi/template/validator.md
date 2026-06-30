# Validator Prompt Template

Dùng prompt này khi Codex harness đã connect sẵn với MCP server
`nli-tools`.

```text
You are connected to MCP server `nli-tools`.

Available MCP resources:
- skill://instructor
- skill://execution
- skill://progress_tracking
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
Validate generated Vietnamese NLI rows through blanked labels:
- input_path: <GENERATED_CSV_WITH_LABEL_COLUMN_RUNTIME_MASKS_LABELS>
- output_dir: data/validated/<DATASET_SLICE>/<MODEL_ID>
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20

Flow:
1. Read MCP resources theo thứ tự:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://validator
2. Call start_validation_run với from_sample, to_sample, và batch_size.
3. Loop:
   - claim_next_validation_batch
   - nếu status=claimed và toàn bộ claimed rows đều nhìn thấy đầy đủ, assign predicted_label chỉ từ premise và hypothesis
   - submit_validation_result với đúng một verdict cho mỗi claimed source_uid và reason tiếng Việt không rỗng
   - nếu status=waiting, inspect progress hoặc release claim bị bỏ dở
   - continue until claim_next_validation_batch returns complete
4. Call verify_validation_progress_log.
5. Call finalize_validation_run.
6. Report run_id, output_path, total_rows, accepted_rows, rejected_rows, and
   unresolved issues.

Rules:
- Use MCP resource reads for the listed `skill://...` resources before calling
  validation tools.
- Truyền generated CSV có label vào start_validation_run. Không dùng masked CSV
  dành cho validator làm runtime input.
- Claimed rows expose only source_uid, premise, hypothesis, and `label=""`.
- Do not read or infer hidden labels from the original file, metadata, row order,
  batch id, or prior outputs.
- Không đọc source CSV hoặc `data/batches/{run_id}` để reconstruct claimed batch.
  Runtime chỉ ghi batch CSV sau `submit_validation_result`.
- Giữ `batch_size=20` trừ khi user approve rõ một giá trị khác.
- Nếu claimed payload bị truncate, thiếu row, hoặc chỉ hiện một phần, coi batch
  đó là unusable: không đoán, không submit partial verdicts, và không backfill
  từ disk. Release claim nếu có thể, rồi báo tooling blocker thay vì đổi
  batch size.
- Không tạo hoặc chạy local orchestration script, thin driver, subprocess
  worker, `fastmcp.Client` loop, `codex exec`, hoặc `claude -p` để xử lý
  validation batch. Nếu Codex subagent nhìn thấy trong Desktop hoặc tool
  response không khả dụng, dừng và báo blocker thay vì tự đổi execution mode.
- Shell commands chỉ được dùng cho inspection/debug nhẹ, ví dụ `rg`, `sed`,
  `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, và read-only progress
  checks. Không dùng Bash/Python scripts để claim, validate, submit, hoặc
  finalize batches.
- Return exactly one label name: entailment, neutral, or contradiction.
- Finalize writes validation_results.csv and cleans both .pipeline run state and
  data/batches/{run_id} after successful verification.
```
