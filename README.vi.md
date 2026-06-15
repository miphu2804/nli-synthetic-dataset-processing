# NLI Synthetic Data Processing

Project tạo dữ liệu NLI tiếng Việt adversarial bằng 19 transformation giữ
nguyên label. LLM harness kết nối qua MCP, xử lý sample range được giao, và ghi
CSV output đã verify.

English README mặc định: [README.md](README.md)

## Chạy Local

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Chạy Container

```bash
docker run --pull=always -p 8000:8000 miphu2804/nli-synthetic-data-processing:latest
```

MCP endpoint:

```text
http://localhost:8000/mcp/
```

## Resources

| Resource | Mục đích |
|----------|----------|
| `skill://instructor` | Đọc đầu tiên để hiểu NLI task, resource map và phase flow |
| `skill://generator` | Transformation rules và generation self-checks |
| `skill://delegation` | Prompt cho stateless parallel worker |
| `skill://progress_tracking` | Local audit, resume và cleanup |
| `skill://execution` | Runtime ownership boundaries |
| `skill://aggregator` | Finalize behavior |
| `skill://validator` | Masked validation scoring rubric và verdict contract |

## Phase Guides

Dùng các docs này khi Codex harness đã connect sẵn với MCP server.

| Phase | Guide | Output |
|-------|-------|--------|
| Project overview | [docs/vi/project-overview.md](docs/vi/project-overview.md) | `Architecture and runtime ownership` |
| Generator | [docs/vi/generator_prompt_template.md](docs/vi/generator_prompt_template.md) | `data/generated/*.csv` |
| Validator | [docs/vi/validator_prompt_template.md](docs/vi/validator_prompt_template.md) | `data/validated/*/validation_results.csv` |

MCP start tools dùng sample range 1-based inclusive:

```text
from_sample=1, to_sample=20  -> 20 rows đầu
from_sample=21, to_sample=40 -> 20 rows tiếp theo
```

Nội bộ progress vẫn ghi `row_offset` và `row_limit` zero-based.

## Runtime State

Progress là append-only JSONL event log tại:

```text
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/progress.jsonl
```

Batch CSV artifacts nằm tại:

```text
data/batches/{run_id}
```

Chỉ MCP runtime tools được ghi progress. Main agent gọi tools tuần tự.
Subagents nhận claimed rows, transform text, và chỉ trả JSON.

Finalize chỉ thành công sau khi merge và verify. Khi thành công, runtime xóa run
state và `data/batches/{run_id}`. Nếu verification fail, runtime giữ artifacts
để debug.
