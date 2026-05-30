# Progress Tracking — Event Log (JSONL)

Append-only JSONL event log. **The log IS the state** — query it to know where you are, what's done, what's skipped. Hash chain per agent for integrity.

**MCP access**: `skill://progress_tracking` — load via `get_skill("progress_tracking")`.

## Event Format

Every event must have:

| Field | What | Example |
|-------|------|---------|
| `id` | Monotonic per-agent (`alice-1`, `alice-2`, ...) | `"alice-3"` |
| `ts` | ISO timestamp | `"2026-05-30T14:02:01Z"` |
| `event` | Event type | `"row.done"`, `"claim"`, ... |
| `agent` | Who wrote this | `"alice"` |
| `prev_hash` | SHA-256 of previous line by THIS agent | `"a1b2c3..."` |

## Per-Agent Hash Chain

Each agent has its own chain. Two agents appending simultaneously won't break each other's hashes.

```
alice:  {"agent":"alice","prev_hash":"0",...}  → hash → {"agent":"alice","prev_hash":"abc",...}
bob:    {"agent":"bob","prev_hash":"0",...}    → hash → {"agent":"bob","prev_hash":"xyz",...}
```

Verify per agent: `grep '"agent":"alice"' progress.jsonl | python3 verify.py`

## Event Types

### `run.start` / `run.end`

```jsonl
{"id":"alice-0","ts":"...","event":"run.start","agent":"alice","prev_hash":"0"}
{"id":"alice-99","ts":"...","event":"run.end","agent":"alice","prev_hash":"...","processed":50}
```

### `claim` — rows this agent will process

```jsonl
{"id":"alice-1","ts":"...","event":"claim","agent":"alice","prev_hash":"...","rows":"1-50"}
```

Other agents skip claimed rows. Prevents duplicate work.

### `unclaim` — release rows (failed, abandoning)

```jsonl
{"id":"alice-2","ts":"...","event":"unclaim","agent":"alice","prev_hash":"...","rows":"41-50","reason":"premise broken"}
```

### `row.done` — one row finished

```jsonl
{"id":"alice-3","ts":"...","event":"row.done","agent":"alice","prev_hash":"...","source_uid":1}
```

### `row.skip` — row failed after retries

```jsonl
{"id":"alice-4","ts":"...","event":"row.skip","agent":"alice","prev_hash":"...","source_uid":5,"reason":"empty","retries":3}
```

### `batch.done` / `batch.fail`

```jsonl
{"id":"alice-5","ts":"...","event":"batch.done","agent":"alice","prev_hash":"...","batch":1,"rows":"1-5","file":"alice_part1.csv"}
{"id":"alice-6","ts":"...","event":"batch.fail","agent":"alice","prev_hash":"...","batch":2,"error":"write timeout"}
```

## Quick Queries

```bash
PROGRESS="progress.jsonl"

# Total done (all agents)
grep -c '"event":"row.done"' $PROGRESS

# Done by me
grep '"event":"row.done"' $PROGRESS | grep -c '"agent":"alice"'

# Check if row is done by anyone
grep '"source_uid":42' $PROGRESS

# What rows are claimed?
grep '"event":"claim"' $PROGRESS

# My next row to process
my_done=$(grep '"event":"row.done"' $PROGRESS | grep -c '"agent":"alice"')
echo "Next: $((my_done + 1))"

# Skipped rows with reasons
grep '"event":"row.skip"' $PROGRESS | jq '{uid:.source_uid, reason}'
```

## Verify Hash Chain

Per-agent verification. Hash chain proves no one tampered with this agent's log.

```bash
grep '"agent":"alice"' progress.jsonl | python3 -c "
import hashlib, json, sys
prev = '0'
for i, line in enumerate(sys.stdin, 1):
    obj = json.loads(line)
    assert obj['prev_hash'] == prev, f'Broken at line {i}'
    prev = hashlib.sha256(line.rstrip('\n').encode()).hexdigest()
print(f'alice chain OK: {i} events')
"
```

## File Location

```
.pipeline/progress.jsonl    ← tracked in git
.pipeline/outputs/          ← gitignored (CSV per agent)
```

## Constraints

- **Append-only** — `>>`, never `>`
- **Per-agent `id`** — `{name}-{N}`, never reuse
- **`agent` field on every line**
- **`prev_hash` per-agent** — hash of previous line by same agent
- **One event per line** — no newlines inside JSON
