# Generator Prompt Template

Dùng prompt này khi Codex harness đã connect sẵn với MCP server
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
1. Read MCP resources theo thứ tự:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://generator_plain hoặc skill://generator_adversarial, khớp với
     generation_policy
2. Call start_generation_run with from_sample and to_sample.
3. Chỉ dùng subagent nếu user request hoặc template hiện tại yêu cầu.
   Subagent phải là Codex worker nhìn thấy trong Desktop session hiện tại,
   không phải `codex exec`, `claude -p`, subprocess, hoặc local worker script.
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
- Use `generator_plain` cho ANLI-derived hoặc source rows đã có quan hệ
  adversarial/NLI.
- Use `generator_adversarial` chỉ khi mục tiêu explicit là tạo biến thể
  adversarial mới có kiểm soát.
- Nếu subagent được yêu cầu rõ, connected harness tự schedule ngoài backend
  state.
- Only MCP runtime tools write progress.
- Subagents, if used, return JSON only and never call MCP tools.
- Không tạo hoặc chạy local orchestration script, thin driver, subprocess
  worker, `fastmcp.Client` loop, `codex exec`, hoặc `claude -p` để xử lý
  generation batch. Nếu Codex subagent nhìn thấy trong Desktop không khả dụng
  hoặc quá chậm, dừng và báo blocker thay vì tự đổi execution mode.
- Giữ `batch_size=20` trừ khi user approve rõ một giá trị khác.
- Shell commands chỉ được dùng cho inspection/debug nhẹ, ví dụ `rg`, `sed`,
  `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, và read-only progress
  checks. Không dùng Bash/Python scripts để claim, transform, submit, hoặc
  finalize batches.
- Batch CSV artifacts are runtime files under data/batches/{run_id}; finalize
  must clean them after successful verification.
```
