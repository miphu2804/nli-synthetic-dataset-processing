# NLI Prompt Refinement

Use this optional flow before large-scale generation when the generator or
validator instructions need calibration.

## Preconditions

- Start MLflow separately and keep its tracking URI available.
- Freeze one calibration source_uid set for comparable rounds.
- Produce exactly three independent verdict CSV or Parquet files. Each file
  must contain `source_uid,predicted_label,reason`.
- Use three real model execution paths supplied by the active harness. Do not
  claim three-model agreement by copying or renaming one model's output.

## Agent Ownership

The main agent owns orchestration and trusted state:

- read skills and call MCP tools;
- prepare the round input and keep expected label values hidden from validators;
- dispatch exactly three validator subagents in parallel;
- validate responses and persist one verdict file per model;
- call `evaluate_prompt_refinement_round`;
- report kappa, decision, MLflow run ID, and proposal artifacts to the user.

Each subagent is a stateless validator. Give it only `source_uid`, `premise`,
`hypothesis`, the 3-class rubric, and its output path identity. It must return
`source_uid,predicted_label,reason` for every assigned row.

Subagent rules:

- Do not read the labeled calibration file or expected label.
- Do not see another subagent's verdicts or reasons.
- Do not call MCP tools, edit instructions, write runtime state, or decide the
  next round.
- Do not impersonate a different model. Three subagents using one model are not
  three-model agreement.

If a subagent returns invalid schema or UID coverage, retry only that model once.
If it still fails, stop the round and report the blocker. Do not duplicate a
successful model's verdict file.

## Flow

1. Load the generation policy being calibrated and generate the calibration
   rows for the frozen source_uid set. Use `skill://generator_plain` for plain
   ANLI-style translation runs and `skill://generator_adversarial` for
   controlled adversarial runs.
2. Load `skill://validator` and dispatch exactly three independent model
   subagents to judge the same generated rows without seeing expected labels.
3. Validate the three returned verdict sets and save one verdict file per model
   in a dedicated round directory.
4. The main agent calls `evaluate_prompt_refinement_round` with the verdict
   directory, generated labeled calibration file path, round number, change
   summary, MLflow tracking URI, experiment name, and `generator_skill_name`.
5. Follow the returned decision:

| Decision | Action |
|----------|--------|
| `needs_prompt_update` | Stop the round. Report `prompt_augment_proposal.json`, `disagreement_rows.csv`, kappa, and MLflow run ID so the user can manually update the prompt. |
| `accepted` | Stop the round. Report kappa and MLflow run ID; no prompt lock or version promotion is performed. |

Fleiss' kappa below `0.85` means the backend creates a proposal artifact with a
`reason`, `suggested_action`, and evidence source_uid list. The backend does not
spawn editor agents, edit prompt files, rerun the round, register prompt
versions, or promote aliases.

When a generator change regenerates calibration text, treat the result as a new
round with the same source_uid set but different item content. Report the new
hash and do not present the kappa delta as a strict same-item comparison.

## Round Integrity

Within a single round, the chosen generator policy instructions and validator
rubric must stay byte-identical from the moment you dispatch the validator
subagents until `evaluate_prompt_refinement_round` returns. Kappa is computed on
verdicts produced by the instructions as they were at dispatch time.

If the user chooses to edit a prompt after a `needs_prompt_update` proposal,
finish or abandon the current round first, then run a new round on the same
source_uid set.

Do not use PMI as a prompt-refinement trigger. PMI belongs to post-generation
artifact analysis and paraphrasing.

## Report

Return:

- verdict file paths;
- kappa and decision;
- `prompt_augment_proposal.json` when present;
- `disagreement_rows.csv`;
- model identifiers;
- bundle ID;
- MLflow run ID;
- blockers or unresolved questions.
