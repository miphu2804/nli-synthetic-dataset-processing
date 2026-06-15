# Progress Tracking - Giải thích

Progress chỉ là local audit log và state để resume trong một run:

```text
.pipeline/runs/{run_id}/
├── manifest.json
└── progress.jsonl

data/batches/{run_id}/
└── batch-00001.csv
```

Main agent local là MCP caller duy nhất. MCP runtime tool là progress writer.
Subagent không đọc hoặc ghi progress. Không push `.pipeline` hoặc runtime batch
CSV lên Git và không dùng để collaborate giữa nhiều người.

## Lifecycle

```text
run.start
  → claim
  → row.done | row.skip
  → batch.done
  → ...
  → merge.done
  → run.end
  → xóa .pipeline/runs/{run_id} và data/batches/{run_id}
```

Nếu verify fail, giữ lại run directory và batch CSV để debug.

Nếu cần retry một claim bị bỏ dở, gọi `release_batch_claim`. MCP runtime append
event `unclaim`, sau đó các row trong batch có thể được claim lại.

`get_run_progress` rebuild snapshot từ event log gồm `done_rows`,
`skipped_rows`, `claimed_rows`, `pending_rows`, `completed_batches`,
`failed_batches` và `active_claims`.

## Resume

Nếu process bị ngắt nhưng container vẫn còn:

1. Gọi `list_generation_runs`.
2. Gọi `get_run_progress(run_id)`.
3. Gọi `release_batch_claim` cho claim bị bỏ dở nếu cần.
4. Tiếp tục claim và submit.
