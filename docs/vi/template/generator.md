# Template Prompt Sinh Dữ Liệu

Dùng prompt này khi Codex harness đã kết nối sẵn với MCP server
`nli-tools`. Thay toàn bộ placeholder bằng giá trị của run hiện tại.

```text
Bạn là main agent đang kết nối MCP server `nli-tools`.

MCP resources có sẵn:
- skill://instructor
- skill://execution
- skill://progress_tracking
- skill://generator_plain
- skill://generator_adversarial
- skill://generator
- skill://delegation
- skill://aggregator

Generation tools có sẵn:
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

Mục tiêu:
Sinh các dòng NLI tiếng Việt từ sample range được giao:
- input_path: "<INPUT_CSV_OR_PARQUET>"
- output_path: "<OUTPUT_CSV_PATH ví dụ data/generated/<RUN_OR_DATASET_ID>.csv>"
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE_OR_END>
- batch_size: <BATCH_SIZE>
- generation_policy: <generator_plain.md_OR_generator_adversarial.md>

Quy trình:
1. Đọc MCP resources theo thứ tự:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://generator_plain hoặc skill://generator_adversarial, khớp với
     generation_policy
2. Gọi start_generation_run với from_sample và to_sample.
3. Chỉ dùng subagent nếu user yêu cầu hoặc template hiện tại yêu cầu.
4. Lặp:
   - claim_next_batch
   - nếu dùng subagent, tạo fresh worker chỉ cho claimed batch đó
   - chuyển đổi từng claimed row theo generation policy đã chọn
   - nếu dùng subagent, chỉ truyền claimed rows cùng batch.artifact_targets
   - nếu dùng subagent, yêu cầu worker ghi rows_csv_path và skipped_rows_csv_path nếu cần, rồi chỉ trả tiny JSON ack
   - tự kiểm tra giữ nguyên label, tiếng Việt tự nhiên, và không lộ cue
   - nếu dùng subagent thì gọi submit_batch_result_from_artifacts
   - nếu không thì gọi submit_batch_result với rows và skipped_rows
   - tiếp tục đến khi claim_next_batch trả complete
5. Gọi verify_progress_log.
6. Đọc skill://aggregator.
7. Gọi finalize_generation_run.
8. Báo cáo run_id, output_path, rows_written, skipped rows, và unresolved issues.

Quy tắc:
- Đọc các MCP resource `skill://...` đã liệt kê trước khi gọi generation tools.
- Dùng `generator_plain` cho ANLI-derived hoặc source rows đã có quan hệ
  adversarial/NLI.
- Dùng `generator_adversarial` chỉ khi mục tiêu explicit là tạo biến thể
  adversarial mới có kiểm soát.
- Nếu subagent được yêu cầu rõ, harness đang kết nối tự schedule ngoài backend
  state.
- Subagent phải là Codex worker nhìn thấy trong Desktop session hiện tại,
  không phải `codex exec`, `claude -p`, subprocess, hoặc local worker script.
- Mỗi worker context chỉ xử lý tối đa một claimed batch. Không reuse cùng worker
  cho nhiều generation batches, vì rows/checks trước đó có thể leak sang quyết
  định của batch sau.
- Chỉ MCP runtime tools được ghi progress.
- Nếu dùng subagent, subagent phải ghi worker CSV artifact vào các path của
  claimed batch, chỉ trả tiny JSON ack, và không bao giờ gọi MCP tools.
- Khi artifact submission đã có sẵn, không paste full batch payload trở lại chat.
- Không tạo hoặc chạy local orchestration script, thin driver, subprocess
  worker, `fastmcp.Client` loop, `codex exec`, hoặc `claude -p` để xử lý
  generation batch. Nếu Codex subagent nhìn thấy trong Desktop không khả dụng
  hoặc quá chậm, dừng và báo blocker thay vì tự đổi execution mode.
- Giữ nguyên batch_size đã yêu cầu trừ khi user approve rõ một giá trị khác.
```
