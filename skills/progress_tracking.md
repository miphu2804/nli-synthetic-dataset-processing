# Progress Tracking — Event Log (JSONL)

Track NLI generation progress with an append-only JSONL event log. Every action is an event with timestamp and causal relation. The log IS the state — no external DB, no memory.

## Event Format

Every event has these required fields:

| Field | What | Example |
|-------|------|---------|
| `ts` | ISO timestamp | `"2026-05-30T14:02:01Z"` |
| `event` | Event type | `"row.processed"` |
| `id` | Unique event id (monotonic) | `"evt_042"` |
| `caused_by` | Parent event id or `null` | `"evt_041"` |

Plus type-specific fields in the event body.

## Event Types

### Run lifecycle

```jsonl
{"ts":"...","event":"run.started","id":"evt_001","caused_by":null,"total_rows":16946,"batch_size":5,"output":"data/anlitrain1_nli_adversarials.csv"}
{"ts":"...","event":"run.completed","id":"evt_099","caused_by":"evt_001","total_processed":50,"skipped":2,"batches_done":10}
```

### Batch lifecycle

```jsonl
{"ts":"...","event":"batch.started","id":"evt_010","caused_by":"evt_001","batch":3,"rows":"11-15"}
{"ts":"...","event":"batch.completed","id":"evt_020","caused_by":"evt_010","batch":3,"written":"data/output_part3.csv","row_count":5}
```

### Row processing (the core event)

```jsonl
{"ts":"...","event":"row.processed","id":"evt_015","caused_by":"evt_010","source_uid":12,"label":"entailment","rule":"Voice flip","tier":"surface","premise_hash":"a1b2c3","hypothesis_hash":"d4e5f6"}
```

### Cache hit / miss

```jsonl
{"ts":"...","event":"row.cached","id":"evt_016","caused_by":"evt_010","source_uid":13,"prompt_hash":"7f8a9b","cache_hit":true}
{"ts":"...","event":"row.cached","id":"evt_017","caused_by":"evt_010","source_uid":14,"prompt_hash":"2c3d4e","cache_hit":false}
```

### Errors & skips

```jsonl
{"ts":"...","event":"row.skipped","id":"evt_018","caused_by":"evt_010","source_uid":15,"reason":"premise empty","retries":3}
{"ts":"...","event":"batch.error","id":"evt_019","caused_by":"evt_010","batch":3,"error":"write_dataset timeout"}
```

### Rule usage snapshot (per batch)

```jsonl
{"ts":"...","event":"rules.snapshot","id":"evt_021","caused_by":"evt_020","counts":{"Voice flip":17,"Scope shift":14,"Direct negation":11,"Fallacious reasoning":9}}
```

## Causal Chain

The `id` + `caused_by` fields form a traceable tree:

```
evt_001 (run.started)
├── evt_010 (batch.started, batch=1)
│   ├── evt_011 (row.processed, uid=1)
│   ├── evt_012 (row.processed, uid=2)
│   ├── evt_013 (row.processed, uid=3)
│   └── evt_014 (batch.completed)
├── evt_020 (batch.started, batch=2)
│   ├── evt_021 (row.cached, cache_hit=true)
│   ├── evt_022 (row.processed, uid=6)
│   └── evt_023 (batch.completed)
└── evt_099 (run.completed)
```

To trace a row back: `row uid=2 → evt_012 → caused_by evt_010 → caused_by evt_001`. Full lineage in 2 hops.

## Quick Queries (bash + grep)

```bash
PROGRESS="progress.jsonl"

# Where am I?
tail -1 $PROGRESS | jq -r '.event'              # last event type
grep '"event":"batch.completed"' $PROGRESS | tail -1 | jq '.batch'  # last done batch

# What's next?
last=$(grep '"event":"row.processed"' $PROGRESS | tail -1 | jq '.source_uid')
echo "Next: $((last + 1))"

# Rule distribution
grep '"event":"row.processed"' $PROGRESS | grep -o '"rule":"[^"]*"' | sort | uniq -c | sort -rn

# Skipped rows
grep '"event":"row.skipped"' $PROGRESS | jq '{uid:.source_uid, reason}'

# Cache hit rate
total=$(grep -c '"event":"row.cached"' $PROGRESS)
hits=$(grep -c '"cache_hit":true' $PROGRESS)
echo "Hit rate: $hits / $total"

# Trace a specific uid
grep '"source_uid":42' $PROGRESS | jq '{event, rule, tier, caused_by}'

# Reconstruct batch 3
grep '"caused_by":"evt_010"' $PROGRESS | jq -c '{event,source_uid,rule,label}'
```

## Cache Integration

When using LLM to transform a row, check cache first:

```bash
# Before calling LLM
prompt_hash=$(echo '{"premise":"...","rule":"Voice flip"}' | md5)
if grep -q "\"prompt_hash\":\"$prompt_hash\",\"cache_hit\":true" $PROGRESS; then
    echo "Cached — skip"
else
    # Call LLM, then record:
    echo '{"ts":"...","event":"row.cached","id":"evt_NNN","caused_by":"evt_XXX","source_uid":99,"prompt_hash":"'$prompt_hash'","cache_hit":false}' >> $PROGRESS
fi
```

## Constraints

- **Always append** — never edit existing lines (`>>`, not `>`)
- **Monotonic ids** — `evt_001`, `evt_002`, ... (increment, never reuse)
- **Timestamp everything** — ISO 8601, seconds precision is enough
- **One event per line** — no pretty-print, no newlines inside JSON
- **caused_by must be valid** — the parent event id must exist in the log
