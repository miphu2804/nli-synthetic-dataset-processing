# Validator Flow

The validator phase checks generated Vietnamese NLI rows under a 3-class scheme
(`0=entailment`, `1=neutral`, `2=contradiction`) with the expected label masked
from the validator. An optional **Layer 0** calibrates the generator and
validator prompts before large-scale generation. The generated corpus then
passes through four layers: per-run blind validation, cross-model consensus,
artifact flagging, and paraphrase application plus semantic revalidation. The
trusted runtime normalizes and strictly validates both sides
(`src/utils/nli_labels.py: require_canonical_label`) so only `0/1/2` and the
canonical names `entailment`/`neutral`/`contradiction` are accepted; any other
value raises before writing output.

## State Machine

Layer 0 — optional prompt refinement before large-scale generation:

```text
fixed labeled calibration dataset
  -> generate with the current generator skill
  -> exactly three independent validators judge the same rows
  -> evaluate_prompt_refinement_round
  -> kappa < 0.85: inspect disagreement_rows.csv and refine prompts
  -> kappa >= 0.85: eligible_to_lock
  -> confirm_lock=true: lock the prompt bundle
  -> start large-scale generation
```

Start MLflow separately; the backend never starts it automatically. Each round
records the calibration dataset hash, both prompt versions, Fleiss' kappa,
verdict files, disagreements, and the bundle decision. Use the same calibration
dataset across rounds so kappa remains comparable. Read
`skill://prompt_refinement` for the agent procedure.

PMI is not a prompt-refinement trigger. It belongs to Layer 3 after generation
and consensus validation.

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
│ entailment | neutral | contradiction  (or 0 | 1 | 2)    │
│ + reason (Vietnamese, must be non-blank)                 │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ submit_validation_result            [deterministic]      │
│ predicted_label validated at schema boundary;            │
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

Layer 2 — cross-model consensus (offline, deterministic CLI). Run Layer 1
**exactly three times** (one model per run) to get exactly three verdict files,
then aggregate. The pipeline implements the paper's `2 of 3` retention rule; the
CLI enforces exactly three files and rejects more or fewer.

**Input contracts:**
- Exactly three verdict files (gpt4o.csv, deepseek.csv, llama.csv or similar).
- Each file: `source_uid, predicted_label, reason` — no null UIDs, no duplicate
  UIDs, no blank reasons, labels in the three-class domain only.
- All three files must share the exact same `source_uid` set.
- The expected-label dataset must share the exact same `source_uid` set.
- The masked dataset must share the exact same `source_uid` set.
- Any mismatch raises before writing output (outputs are staged, then atomically
  replaced — a validation failure never truncates existing files).

```text
┌──────────────────────────────────────────────────────────┐
│ run Layer 1 exactly once per model → verdict files       │
│ gpt4o.csv · deepseek.csv · llama.csv                     │
│ (source_uid, predicted_label, reason)                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli aggregate                              │
│   --verdicts-dir  --masked-input  --expected-input       │
│ agree_count = #models where canonical(pred)==canonical(exp)│
└──────────────────────────────────────────────────────────┘
                              │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ KEEP             │   │ REVIEW           │   │ DISCARD          │
│ agree ≥ 2 of 3   │   │ agree == 1       │   │ agree == 0       │
└──────────────────┘   └──────────────────┘   └──────────────────┘

ALL rows    → validation_votes.csv    (every row + its keep/review/discard decision)
KEEP only   → validated_dataset.csv   (source_uid,premise,hypothesis,label)
REVIEW only → review_dataset.csv      (source_uid,premise,hypothesis + per-model
                                       labels, expected_label, agree_count)
```

`review_dataset.csv` is the manual-review queue (agree == 1). It keeps the full
vote context so a human can see the disagreement; `expected_label` is preserved
(not renamed to `label`) because these rows are unverified and must not be
published as-is. `accepted` (a per-model flag in Layer 1) and `decision`
(cross-model consensus) are different layers.

No MCP tool exists yet for this CLI stage. It is run manually by an operator.

Layer 3 — artifact flagging (deterministic, corpus-level). Run on the
validated/kept rows:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli pmi                                    │
│   --input <validated_dataset.csv> --pmi-threshold T     │
│ PMI computed ONCE over all rows, example-level (Eq. 2)   │
│ default --label-column label                             │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ pmi_artifact_tokens.csv   → (token, label, pmi, …)       │
│ pmi_flagged_rows.csv      → rows whose hypothesis leaks  │
│                             its own label via a token    │
│                             → these must be paraphrased  │
└──────────────────────────────────────────────────────────┘
```

Layer 4 — apply paraphrase (deterministic). The harness paraphrases the
hypotheses in `pmi_flagged_rows.csv` (the LLM step, outside this code), emits a
`source_uid,hypothesis` file of rewrites, then applies them back:

**Input contracts:**
- `--flagged-rows pmi_flagged_rows.csv` is required; do not infer flagged rows
  from the paraphrase file.
- The flagged UID set must equal the paraphrase UID set exactly.
- Every rewrite must be non-empty, changed from the original, and must no longer
  contain any token listed in that row's `artifact_tokens` column.

**Outputs:**
- `paraphrased_dataset.csv` — candidate dataset with rewrites applied.
  **Not final.** Semantic labels for changed rows must be revalidated before
  this file is published.
- `paraphrase_revalidation_masked.csv` — revalidation queue containing only
  the changed rows: `source_uid, premise, hypothesis, masked_label=[MASK]`.
  Feed this file into Layer 1 of a new validation run before promoting the
  paraphrased dataset.

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli apply-paraphrase                       │
│   --input validated_dataset.csv                          │
│   --flagged-rows pmi_flagged_rows.csv                    │
│   --paraphrases <paraphrased.csv>                        │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   paraphrased_dataset.csv          (candidate — awaits revalidation)
   paraphrase_revalidation_masked.csv (next-stage input for Layer 1)
```

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,masked_label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

`predicted_label` must be one of `entailment`, `neutral`, `contradiction`, `0`,
`1`, or `2`. Any other value is rejected at schema validation before the batch is
written.

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
  the runtime maps to numeric ids. `reason` is Vietnamese and must be non-blank.
- `accepted` (per-run, single model) and `decision` (cross-model consensus) are
  different layers: `accepted` = does this one model match `expected_label`;
  `decision` = do ≥ 2 of 3 models match `expected_label`.
- Prompt-calibration kappa is available through
  `evaluate_prompt_refinement_round` and logged to MLflow. The deterministic
  CLI stages `aggregate`, `pmi`, and `apply-paraphrase` remain operator-run.
