# Validator Flow

Validator phase kiểm tra generated Vietnamese NLI rows khi label bị mask khỏi
validator. Trusted runtime giữ hidden label nội bộ và tính verdict có khớp hay
không.

## State Machine

```text
START
  -> đọc skill://instructor
  -> đọc skill://execution
  -> đọc skill://progress_tracking
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

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,masked_label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

## Final Output Schema

```csv
source_uid,premise,hypothesis,expected_label,predicted_label,accepted,reason
```

## Ghi chú

- Chỉ dùng `premise`, `hypothesis`, và label rubric.
- Không suy hidden label từ row order, metadata, batch id, hoặc prior outputs.
- Nếu run dùng numeric labels, trả đúng numeric label id.
