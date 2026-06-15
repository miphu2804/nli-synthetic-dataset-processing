# Progress Tracking

Progress state là local audit state cho active runs. Log là append-only và chỉ
MCP runtime tools được sở hữu quyền ghi.

## Runtime Paths

```text
.pipeline/runs/{run_id}/manifest.json
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/manifest.json
.pipeline/validation/runs/{run_id}/progress.jsonl
data/batches/{run_id}/
```

Batch CSV files trong `data/batches/{run_id}` là runtime artifacts, không phải
final outputs.

## Event Lifecycle

```text
run.start
  -> claim
  -> row.done | row.skip
  -> batch.done
  -> ...
  -> merge.done
  -> run.end
  -> xóa run state và data/batches/{run_id}
```

Validation dùng event name riêng cho start, merge, end, nhưng cùng model claim,
row, batch, verify, và cleanup.

## Cleanup

Finalize chỉ xóa run state và `data/batches/{run_id}` sau khi merge và
verification thành công. Nếu verification fail thì giữ cả hai để debug.

## Resume

Nếu process bị ngắt khi state vẫn còn:

1. Gọi `list_generation_runs` hoặc `list_validation_runs`.
2. Inspect progress bằng progress tool tương ứng.
3. Release abandoned active claims nếu cần.
4. Tiếp tục claim và submit batches.
