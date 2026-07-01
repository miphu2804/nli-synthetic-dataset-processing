# Template Prompt Validation

Dùng prompt này khi Codex harness đã kết nối sẵn với MCP server
`nli-tools`.

Docker connection: `http://localhost:8000/mcp/` sau khi chạy published image
với ports `8000` và `5000` đã publish.

```text
Bạn đang kết nối MCP server `nli-tools`.

MCP resources có sẵn:
- skill://instructor
- skill://execution
- skill://progress_tracking
- skill://validator

Validation tools có sẵn:
- start_validation_run
- claim_next_validation_batch
- submit_validation_result
- submit_validation_result_from_artifact
- get_validation_progress
- release_validation_batch_claim
- verify_validation_progress_log
- finalize_validation_run
- list_validation_runs

Mục tiêu:
Kiểm tra các dòng NLI tiếng Việt đã sinh qua label đã được blank:
- input_path: <GENERATED_CSV_WITH_LABEL_COLUMN_RUNTIME_MASKS_LABELS>
- output_dir: data/validated/<DATASET_SLICE>/<MODEL_ID>
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20

Quy trình:
1. Đọc MCP resources theo thứ tự:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://validator
2. Gọi start_validation_run với from_sample, to_sample, và batch_size.
3. Lặp:
   - claim_next_validation_batch
   - nếu status=claimed và toàn bộ claimed rows đều nhìn thấy đầy đủ, gán predicted_label chỉ từ premise và hypothesis
   - nếu dùng subagent, chỉ truyền claimed rows cùng batch.artifact_targets
   - nếu dùng subagent, yêu cầu worker ghi verdicts_csv_path rồi chỉ trả tiny JSON ack
   - nếu dùng subagent thì gọi submit_validation_result_from_artifact
   - nếu không thì gọi submit_validation_result với đúng một verdict cho mỗi claimed source_uid và reason tiếng Việt không rỗng
   - nếu status=waiting, inspect progress hoặc release claim bị bỏ dở
   - tiếp tục đến khi claim_next_validation_batch trả complete
4. Gọi verify_validation_progress_log.
5. Gọi finalize_validation_run.
6. Báo cáo run_id, output_path, total_rows, accepted_rows, rejected_rows, và
   unresolved issues.

Quy tắc:
- Đọc các MCP resource `skill://...` đã liệt kê trước khi gọi validation tools.
- Truyền generated CSV có label vào start_validation_run. Không dùng masked CSV
  dành cho validator làm runtime input.
- Claimed rows chỉ expose source_uid, premise, hypothesis, và `label=""`.
- Claimed rows cũng kèm artifact_targets để worker ghi CSV verdicts.
- Không đọc hoặc suy hidden labels từ original file, metadata, row order,
  batch id, hoặc prior outputs.
- Không đọc source CSV hoặc `data/batches/{run_id}` để reconstruct claimed batch.
  Runtime chỉ ghi batch CSV sau `submit_validation_result`.
- Giữ `batch_size=20` trừ khi user approve rõ một giá trị khác.
- Nếu claimed payload bị truncate, thiếu row, hoặc chỉ hiện một phần, coi batch
  đó là unusable: không đoán, không submit partial verdicts, và không backfill
  từ disk. Release claim nếu có thể, rồi báo tooling blocker thay vì đổi
  batch size.
- Khi artifact submission đã có sẵn, không paste full verdict batch trở lại
  chat; hãy ghi CSV artifact và chỉ trả tiny JSON ack.
- Không tạo hoặc chạy local orchestration script, thin driver, subprocess
  worker, `fastmcp.Client` loop, `codex exec`, hoặc `claude -p` để xử lý
  validation batch. Nếu Codex subagent nhìn thấy trong Desktop hoặc tool
  response không khả dụng, dừng và báo blocker thay vì tự đổi execution mode.
- Shell commands chỉ được dùng cho inspection/debug nhẹ, ví dụ `rg`, `sed`,
  `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, và read-only progress
  checks. Không dùng Bash/Python scripts để claim, validate, submit, hoặc
  finalize batches.
- Trả đúng một label name: entailment, neutral, hoặc contradiction.
- Finalize ghi validation_results.csv và cleanup cả .pipeline run state lẫn
  data/batches/{run_id} sau khi verification thành công.
```
