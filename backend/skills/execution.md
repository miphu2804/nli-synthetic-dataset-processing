# Execution - Runtime Boundary

Keep text generation and runtime state separate.

| Task | Owner |
|------|-------|
| Translate and transform NLI text | LLM worker |
| Validate semantic label | Main agent |
| Claim, submit, progress, merge and cleanup | MCP runtime tools |
| Dataset slice assignment between users | User-provided `from_sample` and `to_sample` |

## Rules

- Do not generate hypothesis text with Python templates.
- Do not manually edit `.pipeline/runs/{run_id}/progress.jsonl`.
- Do not push `.pipeline` to Git or share it between users.
- Subagents write worker CSV artifacts, return a tiny JSON ack, and never call
  MCP. Main agent performs MCP calls.
- In Codex Desktop, do not replace visible Codex subagents with `codex exec`,
  `claude -p`, subprocess workers, local orchestration scripts, or headless
  `fastmcp.Client` loops unless the user explicitly approves headless mode.
- Keep the requested `batch_size` unchanged unless the user explicitly approves
  changing it.
- Shell commands may be used only for lightweight inspection/debugging, such as
  `rg`, `sed`, `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, and read-only
  progress checks. Do not use Bash/Python scripts to claim, transform, validate,
  submit, or finalize runtime batches.
- Use server-visible project data paths such as `data/original/input.csv` and
  `data/generated/result.csv`.
