# Tổng Quan Project

Project này cung cấp MCP runtime local cho hai phase chính:

- **Generator:** tạo dữ liệu NLI tiếng Việt từ slice nguồn có label. Dùng
  `skill://generator_plain` cho nguồn kiểu ANLI đã có quan hệ adversarial/NLI,
  hoặc `skill://generator_adversarial` khi muốn tạo biến thể adversarial mới có
  kiểm soát.
- **Validator:** validate dữ liệu đã generate bằng label rỗng và để trusted
  runtime so với hidden source label.

## Kiến trúc

```text
Codex harness
  -> đọc MCP resources
  -> dùng from_sample/to_sample
  -> gọi MCP tools tuần tự khi mutate runtime
  -> nhận final data outputs
```

MCP server:

```text
nli-data-processing-mcp-server
  Generation:
    start_generation_run
    claim_next_batch
    submit_batch_result
    verify_progress_log
    finalize_generation_run

  Validation:
    start_validation_run
    claim_next_validation_batch
    submit_validation_result
    verify_validation_progress_log
    finalize_validation_run
```

## Quyền sở hữu

| Owner | Trách nhiệm |
|-------|-------------|
| User | Chia range bằng `from_sample` và `to_sample` |
| Codex harness | Đọc resources, gọi MCP tools, self-check generated rows |
| Subagent | Transform generation rows đã claim và chỉ trả JSON |
| MCP runtime | Claim batches, ghi progress, ghi batch CSV, merge, verify, cleanup |

## Boundary Dataset

`DataProcessingService` sở hữu file-level tabular IO: đọc CSV/parquet cho runtime
path đang chạy, ghi CSV/parquet cho row payload, và convert `.csv`, `.tsv`,
`.parquet`, `.xlsx`, `.xls`, `.jsonl`, cùng JSON array record phẳng về CSV
canonical. Service này không sở hữu generation, validation, post-validation,
random sampling, label normalization, hay hidden cleanup policy.

## Sample Ranges

MCP start tools dùng sample range 1-based inclusive:

```text
from_sample=1, to_sample=20  -> samples 1 đến 20
from_sample=21, to_sample=40 -> samples 21 đến 40
```

Nội bộ service vẫn lưu `row_offset` và `row_limit` zero-based trong manifest và
response. Prompt cho harness nên dùng `from_sample` và `to_sample`.

## Runtime State

Runtime state là local và có thể resume khi run còn active.
Các path bên dưới là relative với repo root; `data/` nằm cùng cấp với
`backend/`, không nằm bên trong `backend/`.

```text
.pipeline/runs/{run_id}/manifest.json
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/manifest.json
.pipeline/validation/runs/{run_id}/progress.jsonl
data/batches/{run_id}/
```

Batch CSV là runtime artifact, không phải final output. Finalize thành công sẽ
merge batch files, check progress consistency và row counts, sau đó xóa cả run
state và `data/batches/{run_id}`. Nếu verification fail thì giữ artifacts để
debug.
