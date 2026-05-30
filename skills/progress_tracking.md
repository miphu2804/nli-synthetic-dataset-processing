# Progress Tracking — Event Log (JSONL)

Track NLI generation progress with an append-only JSONL event log. Every event links to its parent via hash, forming an immutable chain. **The log IS the state** — no external DB, no memory.

## Event Format

Every event must have:

| Field | What | Example |
|-------|------|---------|
| `id` | Monotonic sequence number | `1`, `2`, `3`, ... |
| `ts` | ISO timestamp | `"2026-05-30T14:02:01Z"` |
| `event` | Event type | `"row.done"` |
| `prev_hash` | SHA-256 of previous line (for first event: `"0"`) | `"a1b2c3d4..."` |

Plus type-specific fields.

## Hash Chain

Each line is hashed (full JSON string, including newline) and the hash goes into the **next** line's `prev_hash`. This makes the log tamper-proof:

```
Line 1: {"id":1,"ts":"...","event":"run.start","prev_hash":"0",...}
          → hash(line1) = "abc123"

Line 2: {"id":2,"ts":"...","event":"row.done","prev_hash":"abc123",...}
          → hash(line2) = "def456"

Line 3: {"id":3,"ts":"...","event":"row.done","prev_hash":"def456",...}
```

To verify: `sha256(line_N) == line_N+1.prev_hash` for all N. If any line is edited, the chain breaks.

## Event Types

### 1. `run.start` — first line of every run

```jsonl
{"id":1,"ts":"2026-05-30T14:00:00Z","event":"run.start","prev_hash":"0","input":"data/anlitrain1.csv","total_rows":100,"batch_size":5,"output":"data/anlitrain1_nli_adversarials.csv"}
```

### 2. `run.end` — last line of a completed run

```jsonl
{"id":99,"ts":"2026-05-30T14:30:00Z","event":"run.end","prev_hash":"...","processed":50,"skipped":2}
```

### 3. `row.done` — one row processed successfully

```jsonl
{"id":15,"ts":"2026-05-30T14:02:00Z","event":"row.done","prev_hash":"...","source_uid":12}
```

The most important event. Query it to:
- Check if a row is already processed: `grep '"source_uid":42' progress.jsonl`
- Count rows done: `grep -c '"event":"row.done"' progress.jsonl`
- Resume from: `grep -c '"event":"row.done"' progress.jsonl` + 1

Note: label, rule, tier are in the CSV output — query those files for distribution stats.

### 4. `row.skip` — row failed after retries

```jsonl
{"id":18,"ts":"2026-05-30T14:03:00Z","event":"row.skip","prev_hash":"...","source_uid":15,"reason":"premise too short","retries":3}
```

### 5. `batch.done` — one batch written to file

```jsonl
{"id":20,"ts":"2026-05-30T14:04:00Z","event":"batch.done","prev_hash":"...","batch":3,"rows":"11-15","file":"data/output_part3.csv"}
```

### 6. `batch.fail` — batch write failed

```jsonl
{"id":21,"ts":"2026-05-30T14:05:00Z","event":"batch.fail","prev_hash":"...","batch":4,"error":"write_dataset timeout"}
```

## Causal Chain

Since `prev_hash` links each line to the one before, the full run history is traceable:

```
id:1  (run.start)
  ↓ prev_hash
id:2  (row.done, uid=1)
  ↓ prev_hash
id:3  (row.done, uid=2)
  ↓ prev_hash
...  
  ↓ prev_hash
id:20 (batch.done, batch=3)
  ↓ prev_hash
id:21 (row.done, uid=16)
  ↓ prev_hash
...
  ↓ prev_hash
id:99 (run.end)
```

To trace what happened in batch 3: find `batch.done` with `batch:3` (id:20), then find all `row.done` events between the previous `batch.done` (id:14) and id:20.

## Quick Queries

```bash
PROGRESS="progress.jsonl"

# Resume: where was I?
tail -1 $PROGRESS                          # last event
grep '"event":"row.done"' $PROGRESS | wc -l  # rows done so far
grep '"event":"batch.done"' $PROGRESS | tail -1 | jq '.batch'  # last batch number

# Has this row been processed?
grep '"source_uid":42' $PROGRESS

# Skipped rows with reasons
grep '"event":"row.skip"' $PROGRESS | jq '{uid:.source_uid, reason}'

# Verify hash chain integrity (Python hashlib = C-backed, ~900K events/s)
python3 -c "
import hashlib, json
prev = '0'
with open('progress.jsonl') as f:
    for i, line in enumerate(f, 1):
        obj = json.loads(line)
        assert obj['prev_hash'] == prev, f'Chain broken at line {i}'
        prev = hashlib.sha256(line.rstrip('\n').encode()).hexdigest()
print(f'Chain OK: {i} events, last hash: {prev}')
"
```

## How to Use

1. **Start a run**: append `run.start` with `prev_hash:"0"`
2. **Each row done**: append `row.done` with `prev_hash = sha256(previous line)`
3. **Each batch done**: append `batch.done`
4. **Row failed**: append `row.skip`
5. **Run done**: append `run.end`
6. **Resume**: `grep '"event":"row.done"' progress.jsonl | wc -l` → continue from `count + 1`

## Constraints

- **Append-only** — `>>`, never `>`
- **Monotonic id** — 1, 2, 3, ..., never reuse
- **prev_hash required** — every event links to the previous line's hash
- **One event per line** — no newlines inside JSON
- **Timestamp everything** — ISO 8601, seconds precision
