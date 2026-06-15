# Generator Flow

Generator phase tạo dữ liệu NLI tiếng Việt adversarial từ source slice có label.
Harness đọc resources, claim batch qua MCP, transform rows, self-check, rồi chỉ
submit rows đã validate.

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

## Output Schema

```csv
source_uid,premise,hypothesis,label
```

## Ghi chú

- Dùng `from_sample` và `to_sample` là sample number 1-based inclusive.
- Giữ nguyên source label.
- Không generate hypothesis text bằng Python templates.
- Chỉ MCP runtime tools được ghi progress.
- Subagents có thể transform rows đã claim nhưng chỉ được trả JSON.
