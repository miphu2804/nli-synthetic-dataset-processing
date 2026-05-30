# Aggregator — Merge & Cleanup

Run as the **final step** after all agents finish their batches. Reads progress.jsonl, concats all `part*.csv` into `final.csv`, cleans intermediate files, appends `merge.done`.

## Procedure

1. **Find part files**
```bash
ls .pipeline/outputs/part*.csv
```

2. **Count expected rows** from `batch.done` events:
```bash
grep '"event":"batch.done"' .pipeline/progress.jsonl
```

3. **Merge CSVs** — keep header from first file, skip headers from rest:
```bash
FIRST=$(ls .pipeline/outputs/part*.csv | sort | head -1)
head -1 "$FIRST" > .pipeline/final.csv
for f in .pipeline/outputs/part*.csv; do
  tail -n +2 "$f" >> .pipeline/final.csv
done
```

4. **Verify row count** matches expected.

5. **Clean intermediates** — remove batch JSONs and part CSVs:
```bash
rm -f .pipeline/batch_*.json .pipeline/outputs/part*.csv .pipeline/outputs/batch_*_result.json
```

6. **Append `merge.done` to progress.jsonl** — hash chain by agent `"aggregator"`:
```jsonl
{"id":"aggregator-0","ts":"...","event":"merge.done","agent":"aggregator","prev_hash":"...","processed":200,"file":".pipeline/final.csv","cleanup":true}
```

The prev_hash must be SHA-256 of the previous line by agent `"aggregator"` (or `"0"` if first event for this agent).

## Event

| Field | Value |
|-------|-------|
| `event` | `merge.done` |
| `agent` | `"aggregator"` |
| `processed` | Total rows written |
| `file` | Path to final CSV |
| `cleanup` | `true` (confirms removal of intermediates) |
