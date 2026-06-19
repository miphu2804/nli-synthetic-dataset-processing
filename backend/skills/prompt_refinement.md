# NLI Prompt Refinement

Use this optional flow before large-scale generation when the generator or
validator instructions have not yet been calibrated.

## Preconditions

- Start MLflow separately and keep its tracking URI available.
- Use one fixed labeled calibration dataset across every round. The paper used
  50 samples; this runtime accepts any non-empty size.
- Produce exactly three independent verdict CSV or Parquet files. Each file
  must contain `source_uid,predicted_label,reason`.
- Use three real model execution paths supplied by the active harness. Do not
  claim three-model agreement by copying or renaming one model's output.

## Flow

1. Load `skill://generator` and generate the fixed calibration sample.
2. Load `skill://validator` and ask exactly three independent models to judge
   the same generated rows without seeing expected labels.
3. Save one verdict file per model in a dedicated round directory.
4. Call `evaluate_prompt_refinement_round` with the verdict directory,
   generated labeled calibration file path, round number, change summary, and
   MLflow tracking URI.
5. Follow the returned decision:

| Decision | Action |
|----------|--------|
| `refine_prompt` | Inspect `disagreement_rows.csv`, edit the responsible skill, then repeat on the same calibration dataset. |
| `eligible_to_lock` | Report the candidate versions. Continue refining or explicitly confirm the lock. |
| `lock_prompt` | Report the locked bundle and proceed to large-scale generation. |

Fleiss' kappa below `0.85` means refine. Kappa at least `0.85` is eligible to
lock; it does not lock automatically. To lock, call the tool again for that
eligible round with `confirm_lock=true`.

## Choose What to Edit

- Edit `backend/skills/generator.md` when disagreements come from ambiguous,
  unnatural, or logically incorrect generated hypotheses.
- Edit `backend/skills/validator.md` when disagreements come from unclear
  distinctions between entailment, neutral, and contradiction.
- Edit both only when the disagreement evidence supports both causes.
- Change the smallest instruction needed and describe it in `change_summary`.

Do not use PMI as a prompt-refinement trigger. PMI belongs to post-generation
artifact analysis and paraphrasing.

## Report

Return the changed prompt files, kappa, decision, calibration dataset hash,
generator and validator prompt versions, bundle ID, MLflow run ID, and run URL.
