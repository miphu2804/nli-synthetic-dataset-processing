# Execution - Runtime Boundary

Keep text generation and runtime state separate.

| Task | Owner |
|------|-------|
| Translate and transform NLI text | LLM worker |
| Validate semantic label | Main agent |
| Claim, submit, progress, merge and cleanup | MCP runtime tools |
| Dataset slice assignment between users | User-provided `row_offset` and `row_limit` |

## Rules

- Do not generate hypothesis text with Python templates.
- Do not manually edit `.pipeline/runs/{run_id}/progress.jsonl`.
- Do not push `.pipeline` to Git or share it between users.
- Subagents return JSON only. Main agent performs MCP calls.
- Use container paths such as `/data/input.csv` and `/output/result.csv`.
