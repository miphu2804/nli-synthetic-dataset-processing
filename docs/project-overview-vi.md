# NLI Synthetic Data Processing — Tổng quan

## Dự án làm gì?

Xây pipeline xử lý dữ liệu NLI (Natural Language Inference) tiếng Anh → tiếng Việt, có adversarial transformation. Mục tiêu: tạo dataset NLI tiếng Việt đa dạng về độ khó để huấn luyện và đánh giá model.

## Kiến trúc

```
┌─────────────────────────────────────────────┐
│                 MCP Harness                  │
│  (Claude Code / Codex CLI / custom agent)   │
│                                              │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ generator│ │ progress │ │ delegation  │ │
│  │   .md    │ │_tracking │ │    .md      │ │
│  │          │ │   .md    │ │             │ │
│  │ 19 rules │ │ JSONL log│ │ subagent    │ │
│  │ 3 labels │ │hash chain│ │ orchestrate │ │
│  │ 3 tiers  │ │ queries  │ │ parallel    │ │
│  └──────────┘ └──────────┘ └─────────────┘ │
│                                              │
│  Skills: text guide cho agent đọc và làm     │
└──────────────────────┬──────────────────────┘
                       │ MCP tools
                       ▼
┌─────────────────────────────────────────────┐
│           NLI-Tools Backend                  │
│                                              │
│  /api/datasets/read   — đọc CSV/parquet     │
│  /api/datasets/write  — ghi CSV             │
│  /api/skills/{name}   — đọc skill markdown  │
│  /api/skills/         — list skill          │
│  /health              — health check        │
│  /mcp                 — MCP endpoint        │
└─────────────────────────────────────────────┘
```

## 3 thành phần chính

### 1. Backend (Python/FastAPI)
- Serve REST API + MCP endpoint
- read_dataset: đọc batch từ CSV/parquet
- write_dataset: ghi rows ra CSV
- get_skill: trả về nội dung skill markdown

### 2. Skills (Markdown guide)
- `generator.md`: 19 rule biến đổi, 3 label, 3 adversarial tier
- `progress_tracking.md`: JSONL event log với hash chain
- `delegation.md`: subagent orchestration, parallel execution

### 3. Harness (Agent)
- Đọc skill → hiểu rules + workflow
- Dùng MCP tools (read/write dataset)
- Spawn subagent cho mỗi batch
- Track progress qua JSONL log

## Data flow

```
Input: anlitrain1.csv
  (premise EN, hypothesis EN, label 0/1/2)
          │
          ▼
  ┌─────────────────────┐
  │  Main agent đọc     │
  │  Gán rule + tier    │
  └─────────┬───────────┘
            │
    ┌───────┴───────┐
    ▼               ▼               ▼
Subagent 1      Subagent 2      Subagent 3
(batch 1)       (batch 2)       (batch 3)
    │               │               │
    └───────┬───────┘               │
            ▼                       │
  ┌─────────────────┐              │
  │ Validate + ghi  │◄─────────────┘
  │ part1.csv       │
  │ part2.csv       │
  │ update          │
  │ progress.jsonl  │
  └─────────────────┘
          │
          ▼
Output: anlitrain1_nli_adversarials.csv
  (premise VI, hypothesis VI, label, rule, tier, reason)
```

## Công nghệ

| Lớp | Tech |
|-----|------|
| Backend | Python 3.11+, FastAPI, FastMCP |
| Data | pandas, pyarrow |
| State | JSONL append-only log + hash chain |
| Agent | Markdown skills, MCP tools |
| Model | deepseek-v4-pro (orchestrate), deepseek-v4-flash (transform) |

## Thư mục

```
src/           — Backend code (FastAPI + services + schemas)
skills/        — Agent skill guides (markdown)
docs/          — Tài liệu giải thích tiếng Việt
data/          — Dataset input/output
scripts/       — Utility scripts
```
