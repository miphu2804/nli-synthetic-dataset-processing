# Generator Flow

Generator phase tạo dữ liệu NLI tiếng Việt từ source slice có label. Harness đọc
một generation policy rõ ràng, claim batch qua MCP, transform rows, self-check,
rồi chỉ submit rows đã validate.

## Chọn policy

| Resource | Khi dùng |
|----------|----------|
| `skill://generator_plain` | Source rows đã có quan hệ NLI/adversarial hợp lệ, ví dụ ANLI-derived pairs. Chỉ translate/naturalize, không thêm adversarial transform mới. |
| `skill://generator_adversarial` | Mục tiêu là tạo biến thể Vietnamese NLI adversarial mới có kiểm soát. Translate và apply một rule tương thích label. |
| `skill://generator` | Legacy adversarial alias cho harness prompt cũ. Run mới nên dùng policy explicit. |

## State Machine

```text
START
  -> đọc skill://instructor
  -> đọc skill://execution
  -> đọc skill://progress_tracking
  -> chọn và đọc skill://generator_plain hoặc skill://generator_adversarial
  -> start_generation_run(from_sample, to_sample)
       tạo .pipeline/runs/{run_id}
       tạo data/batches/{run_id}
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

## Output Schema

```csv
source_uid,premise,hypothesis,label
```

## Ghi chú

- Dùng `from_sample` và `to_sample` là sample number 1-based inclusive.
- Giữ nguyên source label.
- Chỉ load một generation policy cho mỗi run, trừ khi user yêu cầu so sánh
  policy.
- Không generate hypothesis text bằng Python templates.
- Chỉ MCP runtime tools được ghi progress.
- Việc fan-out sang subagent thuộc agent. Backend không tính và không áp worker
  plan.
- Subagents có thể transform rows đã claim nhưng chỉ được trả JSON.
