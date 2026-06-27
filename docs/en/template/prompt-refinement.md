# Prompt Refinement Orchestration Template

Use this prompt when Codex is connected to MCP server `nli-tools` and the
operator has already started the required services.

```text
You are the main agent connected to MCP server `nli-tools`.

Goal:
Run one prompt-refinement calibration for the selected NLI generation policy and
validator rubric.

Inputs:
- calibration_source: <FIXED_LABELED_DATASET_OR_SLICE>
- sample_count: <N>
- generator_skill_name: <generator_plain_OR_generator_adversarial_OR_generator>
- output_root: data/prompt-refinement/<SESSION_ID_OR_DATASET_ID>
- tracking_uri: <MLFLOW_TRACKING_URI>
- experiment_name: <MLFLOW_EXPERIMENT_NAME>
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>

Required MCP resources:
- skill://instructor
- skill://prompt_refinement
- skill://validator
- skill://<generator_skill_name>

Task:
1. Read only the required MCP resources and the provided calibration_source.
2. Freeze the selected source_uid set for this calibration.
3. Create output_root/calibration/calibration.csv with:
   source_uid,premise,hypothesis,label
4. Give each validator only masked rows:
   source_uid,premise,hypothesis
5. Run exactly three independent validator models/subagents.
   If three independent models are unavailable, stop and report a blocker.
6. Save one verdict file per model under:
   output_root/calibration/verdicts/<model-id>.csv

Verdict schema:
source_uid,predicted_label,reason

Reject a verdict set with missing UID, duplicate UID, invalid label, blank
reason, or incomplete UID coverage. Retry only the failed model once.

Then call:
evaluate_prompt_refinement(
  verdicts_dir="output_root/calibration/verdicts",
  calibration_input="output_root/calibration/calibration.csv",
  tracking_uri="<MLFLOW_TRACKING_URI>",
  experiment_name="<MLFLOW_EXPERIMENT_NAME>",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Decision handling:
1. If decision=accepted, stop and report the calibration result.
2. If decision=needs_prompt_update, call:
   propose_prompt_refinement_update(
     verdicts_dir="output_root/calibration/verdicts",
     calibration_input="output_root/calibration/calibration.csv",
     generator_skill_name="<GENERATOR_SKILL_NAME>"
   )
3. Stop and report the returned proposal, rejected sample count, and
   disagreement_rows.csv from the same MLflow run so the user can decide which
   prompt to update manually.

Rules:
- Do not read hidden labels outside calibration_source preparation.
- Validator subagents remain blind. Do not expose labels, expected label
  values, or peer verdicts to them.
- Validator subagents do not call MCP tools or write runtime state.
- Do not inspect unrelated repository files.
- Do not edit generator or validator instructions during calibration.
- Do not use PMI in this loop.
- Do not register prompt versions, promote aliases, or lock prompts.
- If MCP or MLflow is unavailable, report the blocker; do not start services.

Report:
- verdict file paths
- kappa and decision
- rejected sample count
- propose_prompt_refinement_update result if called
- disagreement_rows.csv
- bundle ID
- MLflow run ID
- blockers or unresolved questions
```
