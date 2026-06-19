# NLI Prompt Refinement

Use this optional flow before large-scale generation when the generator or
validator instructions have not yet been calibrated.

## Preconditions

- Start MLflow separately and keep its tracking URI available.
- Freeze one calibration source UID set across rounds. The paper used 50
  samples; this runtime accepts any non-empty size.
- Produce exactly three independent verdict CSV or Parquet files. Each file
  must contain `source_uid,predicted_label,reason`.
- Use three real model execution paths supplied by the active harness. Do not
  claim three-model agreement by copying or renaming one model's output.

## Agent Ownership

The main agent owns orchestration and all trusted state:

- read skills and call MCP tools;
- prepare the round input and keep expected labels hidden;
- dispatch exactly three validator subagents in parallel;
- validate responses and persist one verdict file per model;
- call `evaluate_prompt_refinement_round`;
- inspect disagreements, edit prompt skills, and decide whether to confirm lock.

Each subagent is a stateless validator. Give it only `source_uid`, `premise`,
`hypothesis`, the 3-class rubric, and its output path identity. It must return
`source_uid,predicted_label,reason` for every assigned row.

Subagent rules:

- Do not read the labeled calibration file or expected label.
- Do not see another subagent's verdicts or reasons.
- Do not call MCP tools, edit prompt files, write runtime state, or decide to
  lock.
- Do not impersonate a different model. Three subagents using one model are not
  three-model agreement.

If a subagent returns invalid schema or UID coverage, retry only that model once.
If it still fails, stop the round and report the blocker. Do not duplicate a
successful model's verdict file.

## Flow

1. Load `skill://generator` and generate the calibration rows for the frozen
   source UID set. If only validator instructions changed, reuse the same
   generated calibration file. If generator instructions changed, regenerate
   the same source UID set and record the new round hash.
2. Load `skill://validator` and dispatch exactly three independent model
   subagents to judge the same generated rows without seeing expected labels.
3. Validate the three returned verdict sets and save one verdict file per model
   in a dedicated round directory.
4. The main agent calls `evaluate_prompt_refinement_round` with the verdict
   directory, generated labeled calibration file path, round number, change
   summary, and MLflow tracking URI.
5. Follow the returned decision:

| Decision | Action |
|----------|--------|
| `refine_prompt` | Inspect `disagreement_rows.csv`, edit the responsible skill, then repeat on the same calibration dataset. |
| `eligible_to_lock` | Report the candidate versions. Continue refining or explicitly confirm the lock. |
| `lock_prompt` | Report the locked bundle and proceed to large-scale generation. |

Fleiss' kappa below `0.85` means refine. Kappa at least `0.85` is eligible to
lock; it does not lock automatically. To lock, call the tool again for that
eligible round with `confirm_lock=true`.

Do not edit prompt files between subagent dispatch and MCP evaluation. After an
`eligible_to_lock` result, keep the prompt files and verdict inputs unchanged
until confirmation.

When a generator change regenerates calibration text, treat the result as a new
round with the same source UID set but different item content. Report the new
hash and do not present the kappa delta as a strict same-item comparison.

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
generator and validator prompt versions, model identifiers, bundle ID, MLflow
run ID, and run URL. Retrieve `disagreement_rows.csv` from that run's MLflow
Artifacts tab when refinement is required.
