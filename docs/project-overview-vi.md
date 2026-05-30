# NLI Synthetic Data Processing — Tổng quan

## Dự án làm gì?

Pipeline xử lý dữ liệu NLI tiếng Anh → tiếng Việt, có adversarial transformation. Mục tiêu: tạo dataset NLI tiếng Việt đa dạng về độ khó.

## Kiến trúc

```
┌──────────────────────────────────────────────────┐
│                  MCP Harness                       │
│   (Claude Code / Codex CLI / custom agent)        │
│                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │ generator│ │ progress │ │delegation│ │exec  │ │
│  │   .md    │ │_tracking │ │   .md    │ │ .md  │ │
│  │          │ │   .md    │ │          │ │      │ │
│  │19 rules  │ │JSONL log │ │subagent  │ │LLM   │ │
│  │3 labels  │ │per-agent │ │handoff   │ │vs    │ │
│  │3 tiers   │ │hash chain│ │parallel  │ │bash  │ │
│  │          │ │claims    │ │multi-agt │ │monty │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────┘ │
│                                                    │
│  Skills: text guide cho agent đọc và thực thi       │
└───────────────────────┬──────────────────────────┘
                        │ MCP tools
                        ▼
┌──────────────────────────────────────────────────┐
│              NLI-Tools Backend                     │
│  /api/datasets/read   — đọc CSV/parquet           │
│  /api/datasets/write  — ghi CSV                   │
│  /api/skills/{name}   — đọc skill markdown        │
│  /api/skills/         — list skill                │
│  /health              — health check              │
│  /mcp                 — MCP endpoint              │
└──────────────────────────────────────────────────┘
```

## 4 Skills

| Skill | Vai trò |
|-------|---------|
| `generator.md` | WHAT: 19 rule, 3 label, 3 tier, anti-artifact constraints |
| `progress_tracking.md` | STATE: JSONL log, per-agent hash chain, claim, query |
| `delegation.md` | HOW: subagent handoff, parallel execution, multi-agent sync |
| `execution.md` | RUN: LLM cho text, bash cho query, Monty cho untrusted code |

## Data Flow

```
Input: dataset.csv (premise EN, hypothesis EN, label)
  → Agent đọc skill, claim row
  → Subagent dịch + adversarial transform
  → Validate + ghi CSV + append progress.jsonl
  → Merge part files
Output: dataset_nli_adversarials.csv
  (premise VI, hypothesis VI, label, rule, tier, reason)
```

## Công nghệ

| Lớp | Tech |
|-----|------|
| Backend | Python 3.11+, FastAPI, FastMCP |
| Data | pandas, pyarrow |
| State | `.pipeline/progress.jsonl` — append-only, per-agent hash chain |
| Agent | Markdown skills, MCP tools |
| Model | Orchestration: model lớn. Transform: model nhỏ. |

## Thư mục

```
src/           — Backend (FastAPI + services + schemas + routers)
skills/        — Agent skill guides (4 markdown files)
docs/          — Tài liệu tiếng Việt
data/          — Dataset input
.pipeline/     — Runtime (progress.jsonl + outputs) — gitignored except log
```
