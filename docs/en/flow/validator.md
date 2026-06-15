# Validator Flow

The validator phase checks generated Vietnamese NLI rows under a 3-class scheme
(`0=entailment`, `1=neutral`, `2=contradiction`) with the expected label masked
from the validator. There are three layers: a **per-run** blind check that one
model produces (deterministic `accepted`), a **cross-model consensus** that
combines several per-run verdict files into a keep/review/discard `decision`, and
a deterministic **artifact-flagging** pass that finds label-leaking tokens. The
trusted runtime canonicalizes both sides (`src/utils/nli_labels.py:
canonical_label`) so a numeric expected label and a string predicted label
compare correctly.

## State Machine

Layer 1 — per-run blind check (one validator model). This is the main run loop:

```text
┌──────────────────────────────────────────────────────────┐
│ read skills:                                             │
│ instructor · execution · progress_tracking · validator   │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ start_validation_run(from_sample, to_sample)             │
│ • .pipeline/validation/runs/{run_id}                     │
│ • data/batches/{run_id}                                  │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ claim_next_validation_batch                              │
│ → source_uid, premise, hypothesis,                       │
│   masked_label=[MASK]   (expected_label is hidden)       │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ validator predicts 3-class label                         │
│ entailment | neutral | contradiction                     │
│ + reason (Vietnamese)                                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ submit_validation_result            [deterministic]      │
│ runtime joins hidden expected_label, then computes       │
│ accepted = canonical(pred) == canonical(expected)        │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ claim loop                                               │
│ claimed  → predict & submit  (back to predict step)      │
│ waiting  → inspect / release abandoned claim             │
│ complete → verify_validation_progress_log                │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ finalize_validation_run                                  │
│ ok   → validation_results.csv ; run state wiped          │
│ fail → runtime artifacts kept for debugging              │
└──────────────────────────────────────────────────────────┘
```

Layer 2 — cross-model consensus (offline, deterministic CLI). Run Layer 1 once
per model to get N verdict files, then aggregate:

```text
┌──────────────────────────────────────────────────────────┐
│ run Layer 1 once per model →  verdict files              │
│ gpt4o.csv · deepseek.csv · llama.csv · …                 │
│ (source_uid, predicted_label, reason)                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli aggregate                              │
│   --verdicts-dir  --masked-input  --expected-input       │
│ agree_count = #models canonical(pred)==canonical(exp)    │
└──────────────────────────────────────────────────────────┘
                              │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ KEEP             │   │ REVIEW           │   │ DISCARD          │
│ agree ≥ 2        │   │ agree == 1       │   │ agree == 0       │
└──────────────────┘   └──────────────────┘   └──────────────────┘

KEEP → validation_votes.csv (+ pmi_consensus.csv: PMI on the KEPT subset)
```

Layer 3 — artifact flagging (deterministic, corpus-level). Run on the
validated/kept rows:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli pmi                                    │
│   --input <kept.csv>  --pmi-threshold T                  │
│ PMI computed ONCE over all rows (corpus-level)           │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ pmi_artifact_tokens.csv   → (token, label, pmi, …)       │
│ pmi_flagged_rows.csv      → hypotheses whose token       │
│                             leaks its own expected_label │
│                             → paraphrase these           │
└──────────────────────────────────────────────────────────┘
```

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,masked_label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

## Per-run Final Output Schema

```csv
source_uid,premise,hypothesis,expected_label,predicted_label,accepted,reason
```

## Consensus Vote Table Schema

```csv
source_uid,<model>_label...,expected_label,agree_count,decision
```

## Notes

- Use only `premise`, `hypothesis`, and the rubric; never infer the hidden label
  from row order, metadata, batch id, or prior outputs.
- Return one of the 3 canonical names (`entailment`|`neutral`|`contradiction`);
  the runtime maps to numeric ids. `reason` is Vietnamese.
- `accepted` (per-run, single model) and `decision` (cross-model consensus) are
  different layers: `accepted` = does this one model match `expected_label`;
  `decision` = do >= 2 of N models match `expected_label`.
