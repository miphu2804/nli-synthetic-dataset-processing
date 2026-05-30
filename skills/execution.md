# Execution — Python, Bash, and Monty Sandbox

Rule for how to execute code in this pipeline.

## Core Principle

**LLM generates text, not code.** Hypothesis creation must come from the model's language ability — that's where creativity lives. Python scripts generating samples produce rigid, template-like output.

| Task | How | Why |
|------|-----|-----|
| Generate hypothesis text | LLM directly | Creative, natural, varied |
| Translate premise/hypothesis | LLM directly | Preserves nuance |
| Validate label after transform | LLM judgment | Requires semantic understanding |
| Verify hash chain | `uv run python` one-liner | Math, not language |
| Query progress.jsonl | `grep` / `jq` | Faster, no context cost |
| Run untrusted Python code | Monty sandbox | Safety |

## Bash Commands

### Allowed patterns

```bash
# Direct grep/jq — fastest, no context bloat
grep -c '"event":"row.done"' progress.jsonl
tail -1 progress.jsonl | jq '.source_uid'

# Python one-liners via uv run — for math/hash work
uv run python -c "import hashlib; ..."

# Pipe chains — composable
grep '"event":"row.done"' progress.jsonl | wc -l
```

### Forbidden patterns

```
✗ python generate_samples.py        — no creativity
✗ python transform_batch.py         — template output
✗ python -c "long pipeline..."      — >5 lines → use Monty
```

## Monty Sandbox

Pydantic Monty (`pip install pydantic-monty`) is a secure Python interpreter in Rust. Use it when you need to run Python that you don't fully trust — AI-generated code, user scripts, or multi-step data transforms.

### When to use Monty

| Scenario | Use |
|----------|-----|
| AI-generated validation logic | Monty |
| User-submitted transformation rules | Monty |
| Multi-step data reshaping (>5 lines Python) | Monty |
| Hash verify, simple math | `uv run python` (stdlib, safe) |

### How to use

```bash
# Install once
uv add pydantic-monty

# Execute code safely (no fs, no network, no import of dangerous modules)
uv run monty -c "
result = 0
for i in range(100):
    result += i
print(result)
"

# Or pipe code in
echo 'print(sum(range(100)))' | uv run monty
```

### Monty safety model

| Allowed | Blocked |
|---------|---------|
| Basic Python (functions, loops, comprehensions) | `import` (except whitelisted modules) |
| Math operations | Filesystem access |
| String manipulation | Network calls |
| Type hints, f-strings, dataclasses | `exec`, `eval`, `__import__` |
| asyncio | Environment variables |

### Cleanup

Monty runs in-process, no containers to clean up. After execution, memory is freed automatically.

```bash
# Nothing to clean — Monty is not a container, no dangling processes
# If you do spawn subprocesses via bash, clean them:
trap 'kill 0' EXIT  # auto-kill child processes on exit
```

## Decision Flow

```
Need to run code?
  ├─ Is it text generation (hypothesis, translation)?
  │   → LLM does it directly
  │
  ├─ Is it a single query (count, grep, tail)?
  │   → bash grep/jq
  │
  ├─ Is it math/hash (verify, checksum)?
  │   → uv run python -c "oneliner"
  │
  └─ Is it complex logic (>5 lines) or untrusted source?
      → Monty sandbox
```
