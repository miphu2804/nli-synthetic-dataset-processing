# Validator Flow

The validator phase checks generated Vietnamese NLI rows under a 3-class scheme
(`0=entailment`, `1=neutral`, `2=contradiction`) with the expected label masked
from the validator. An optional **Layer 0** calibrates the generator and
validator prompts before large-scale generation. The generated corpus then
passes through four layers: per-run blind validation, cross-model consensus,
artifact flagging, and paraphrase application plus semantic revalidation. The
trusted runtime normalizes and strictly validates both sides
(`src/utils/nli_labels.py: require_supported_nli_label`) so only `0/1/2` and the
supported label names `entailment`/`neutral`/`contradiction` are accepted; any other
value raises before writing output.

## State Machine

Layer 0 — optional prompt refinement before large-scale generation:

```text
fixed labeled calibration dataset
  -> generate with the selected generator policy
  -> exactly three independent validators judge the same rows
  -> evaluate_prompt_refinement_round
  -> kappa < 0.85: prepare_prompt_refinement_evidence_pack
  -> orchestrator spawns editor subagents with static editor templates
  -> refine prompts
  -> kappa >= 0.85: eligible_to_lock
  -> confirm_prompt_lock: lock the prompt bundle after approval
  -> start large-scale generation
```

Start MLflow separately; the backend never starts it automatically. Each round
records the prompt versions, Fleiss' kappa, verdict files, disagreements, and
the bundle decision. Keep the same calibration source UID set across comparable
rounds by operator convention. If the selected generator policy changes,
regenerate that UID set; if only the validator prompt changes, reuse the same
generated calibration file. Read
`skill://prompt_refinement` for the agent procedure.

The Codex main agent owns MCP calls, prompt edits, and file persistence. It
dispatches three isolated validator subagents; each receives masked rows only
and returns verdicts without reading expected labels or other models' outputs.
Prompt files stay unchanged from subagent dispatch through MCP evaluation.

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
│   label=""   (expected_label is hidden)                  │
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
│ accepted = normalize(pred) == normalize(expected)        │
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
│ agree_count = #models where normalize(pred)==normalize(exp)│
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

An operator can run this layer through the `aggregate` CLI. MCP exposes only the
combined `run_consensus_pmi` wrapper after aggregation + PMI share a stable
contract.

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

The operator can run Layer 2 + Layer 3 with one command to persist all artifacts
to a standard output directory:

```bash
python -m src.cli consensus-pmi \
  --verdicts-dir <verdicts_dir> \
  --masked-input <validation_masked.csv> \
  --expected-input <labeled_dataset.csv> \
  --output-dir data/validated/<run_or_dataset_id> \
  --yes
```

When `--output-dir` is omitted, the default is
`data/validated/<expected-input-stem>`.
The equivalent MCP wrapper is `run_consensus_pmi`; it is still deterministic,
does not call a model, and writes the same artifact set to the same output
convention.

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
  the changed rows: `source_uid, premise, hypothesis, label=""`.

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
   paraphrase_revalidation_masked.csv (changed-row revalidation queue)
```

Layer 5 — promote paraphrases after semantic revalidation. Run exactly three
validators on `paraphrase_revalidation_masked.csv`, with each model producing
one `source_uid,predicted_label,reason` verdict file. Then use trusted labels to
promote only rewrites that still preserve the intended label under the `2 of 3`
rule:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli promote-paraphrase                     │
│   --input paraphrased_dataset.csv                        │
│   --revalidation-input paraphrase_revalidation_masked.csv │
│   --verdicts-dir <revalidation_verdicts_dir>              │
│   --expected-input validated_dataset.csv                  │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   promoted_dataset.csv                 (publishable candidate)
   paraphrase_revalidation_votes.csv    (all changed rows + decisions)
   paraphrase_revalidation_review.csv   (review/discard changed rows)
```

`promoted_dataset.csv` keeps unchanged rows and changed rows whose revalidation
decision is `keep`. Changed rows with `review` or `discard` are removed from the
publishable output and written to the review artifact.
The equivalent MCP wrapper is `promote_paraphrase_revalidation`; it calls the
same deterministic CLI logic and still requires exactly three verdict files.

Layer 6 — final grouped-stratified split with premise anti-leakage. Run this
only after a publishable final dataset exists, usually `promoted_dataset.csv`
when PMI/paraphrase rewrote rows, or `validated_dataset.csv` when no row needed
paraphrasing. The split keeps every hypothesis with the same `premise` in the
same set to prevent train/dev/test leakage, then greedily balances row counts
plus label distribution. If a domain/subdomain column is available, you may pass
it to preserve that distribution too.

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli split                                  │
│   --input promoted_dataset.csv                           │
│   --output-dir data/splits/<run_or_dataset_id>            │
│   --group-column premise                                 │
│   --domain-column subdomain   # optional                 │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   train.csv
   dev.csv
   test.csv
   split_manifest.json  (strategy, seed, ratios, row/group counts,
                         label distribution, optional domain status/distribution)
```

The default ratio is `0.8/0.1/0.1`, with default seed `13`, and the default
strategy is grouped-stratified. Override with `--train-ratio`, `--dev-ratio`,
`--test-ratio`, and `--seed`; the ratio sum must be `1.0`.

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,label
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
- Return one of the 3 supported label names (`entailment`|`neutral`|`contradiction`);
  the runtime maps to numeric ids. `reason` is Vietnamese and must be non-blank.
- `accepted` (per-run, single model) and `decision` (cross-model consensus) are
  different layers: `accepted` = does this one model match `expected_label`;
  `decision` = do ≥ 2 of 3 models match `expected_label`.
- Prompt-calibration kappa is available through
  `evaluate_prompt_refinement_round` and logged to MLflow. The deterministic
  CLI stages `aggregate`, `pmi`, and `apply-paraphrase` remain operator-run.
  The combined/stable stages `consensus-pmi` and `promote-paraphrase` also have
  thin MCP wrappers: `run_consensus_pmi` and
  `promote_paraphrase_revalidation`.
