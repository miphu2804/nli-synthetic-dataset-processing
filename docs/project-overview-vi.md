# NLI Synthetic Data Processing - Tổng quan

Pipeline tạo dữ liệu NLI tiếng Việt adversarial từ dataset tiếng Anh đã có label.

## Kiến trúc

```text
┌──────────────────────────────────────────────────────────┐
│                     LLM Harness                          │
│          (Claude Code / Codex CLI / custom agent)        │
│                                                          │
│  skill://instructor: NLI task, resource map, phase flow  │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐   │
│  │generator │ │ progress │ │delegation│ │ execution  │   │
│  │          │ │ tracking │ │          │ │            │   │
│  │19 rules  │ │JSONL log │ │stateless │ │LLM worker  │   │
│  │3 labels  │ │hash chain│ │subagent  │ │MCP runtime │   │
│  │self-check│ │resume    │ │parallel  │ │boundaries  │   │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘   │
│                                                          │
│  aggregator: hướng dẫn finalize local run                │
│  validator: phase dự kiến, chưa có resource              │
│                                                          │
│  User chia slice bằng row_offset + row_limit             │
│  Main agent gọi MCP, self-check output và refill slot    │
└──────────────────────────┬───────────────────────────────┘
                           │ MCP tools
                           ▼
┌──────────────────────────────────────────────────────────┐
│                 NLI-Tools MCP Backend                    │
│                                                          │
│  start_generation_run      → tạo local run               │
│  calculate_dispatch_plan   → tính sliding window         │
│  claim_next_batch          → claim local batch           │
│  submit_batch_result       → ghi CSV + append progress   │
│  finalize_generation_run   → merge, verify, cleanup      │
│                                                          │
│  State: .pipeline/runs/{run_id}/progress.jsonl           │
│  Batch CSV: data/batches/{run_id}/                       │
│  Endpoint: http://localhost:8000/mcp/                    │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
                    output CSV cuối
```

## Quyền sở hữu

| Thành phần | Trách nhiệm |
|------------|-------------|
| User | Chia slice bằng offset và limit |
| Main agent | Gọi MCP, claim, self-check generation output, submit, finalize |
| Subagent | Dịch và transform text, trả JSON |
| MCP server | Local progress, merge, verify, cleanup |

## State

`.pipeline/runs/{run_id}` chỉ tồn tại trong lúc xử lý. Batch CSV trong lúc chạy
nằm ở `data/batches/{run_id}`. Finalize thành công sẽ xóa state và batch CSV.
Mỗi người chạy local riêng, không sync progress qua Git.

## Skill map

| Resource | Khi đọc |
|----------|---------|
| `skill://instructor` | Đọc đầu tiên để hiểu NLI task, resource map và phase flow |
| `skill://execution` | Đọc trước khi xử lý để hiểu runtime boundary |
| `skill://progress_tracking` | Đọc trước khi start hoặc resume local run |
| `skill://generator` | Đọc trước khi generate row |
| `skill://delegation` | Đọc khi xử lý ít nhất `100` row bằng subagent |
| `skill://aggregator` | Đọc trước khi finalize |

## Phase dự kiến

Validation phase sẽ được tách riêng để kiểm tra output sau generation. Hiện tại
chưa có `skill://validator`; agent không tự suy diễn hoặc gọi resource này.
