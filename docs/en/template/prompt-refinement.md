# Prompt Refinement Orchestration Template

Use this prompt in Codex when the harness can execute three independent model
subagents and is connected to MCP server `nli-tools`.

```text
You are the main agent connected to MCP server `nli-tools`.

Goal:
Calibrate the selected NLI generator policy and validator prompt before
large-scale generation.

Inputs:
- calibration_source: <FIXED_SOURCE_DATASET_OR_SLICE>
- generator_skill_name: <generator_plain_OR_generator_adversarial_OR_generator>
- output_root: outputs/prompt-refinement
- experiment_name: nli-prompt-calibration
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_PATHS>

Required resources:
- skill://instructor
- skill://generator_plain or skill://generator_adversarial
- skill://validator
- skill://prompt_refinement

Main agent responsibilities:
1. Read all required resources.
2. Freeze one source_uid set for all rounds.
3. Generate output_root/round-<NN>/calibration.csv with the chosen generator
   policy.
4. Prepare masked rows containing only source_uid, premise, and hypothesis.
5. Dispatch exactly three validator subagents in parallel, one per real model.
6. Validate each response and persist one verdict file per model with:
   source_uid,predicted_label,reason
   under output_root/round-<NN>/verdicts/<model-id>.csv.
7. Call evaluate_prompt_refinement_round.
8. Retrieve disagreement_rows.csv from the MLflow run Artifacts tab and edit
   the smallest responsible prompt:
   the chosen generator policy file, backend/skills/validator.md, or both.
9. Repeat while decision=refine_prompt.
10. When decision=eligible_to_lock, report the round and ask for confirmation.
    Call confirm_prompt_lock(lock_run_id=<MLFLOW_RUN_ID>) only after confirmation.

MCP evaluation call:
evaluate_prompt_refinement_round(
  verdicts_dir="outputs/prompt-refinement/round-<NN>/verdicts",
  calibration_input="outputs/prompt-refinement/round-<NN>/calibration.csv",
  round_number=<NN>,
  change_summary="<PROMPT_CHANGES_TESTED_THIS_ROUND>",
  tracking_uri="http://127.0.0.1:5000",
  experiment_name="nli-prompt-calibration",
  session_id="<OPTIONAL_SESSION_ID_TO_GROUP_ROUNDS>",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Confirmation call (after eligible_to_lock):
confirm_prompt_lock(
  lock_run_id="<MLFLOW_RUN_ID_FROM_ELIGIBLE_ROUND>",
  tracking_uri="http://127.0.0.1:5000"
)

Subagent contract:
- Receive only masked rows and the 3-class validator rubric.
- Return one verdict for every source_uid.
- Write every reason in Vietnamese.
- Do not read the labeled input or expected label.
- Do not see another subagent's output.
- Do not call MCP tools, edit files, write runtime state, or decide lock status.
- Do not impersonate another model.

Failure handling:
- Reject a verdict set with missing/duplicate UIDs, blank reason, or invalid label.
- Retry only the failed model once.
- If it still fails, stop the round; never copy another model's verdict file.
- If three independent model paths are unavailable, report a blocker instead of
  claiming Fleiss kappa.
- If MLflow is unavailable after verdict generation, keep the local files and
  retry the MCP evaluation without rerunning the models.

Prompt integrity:
- Do not edit prompt files between subagent dispatch and MCP evaluation.
- After eligible_to_lock, you can safely edit prompts if you wish to continue
  refining. The confirmed lock will always reference the exact versions that
  were evaluated, not the current files.
- If a generator edit changes calibration text, keep the same source_uid set,
  report the new hash, and do not describe the kappa delta as a strict same-item
  comparison.

Report after every round:
- changed prompt files
- model identifiers/configuration and verdict file paths
- kappa and decision
- calibration dataset hash
- generator and validator prompt versions
- bundle ID, MLflow run ID, and run URL

If you provided a `session_id`, MLflow will create a parent run
`calibration-session-<SESSION_ID>` that aggregates kappa and disagreement
trends across all rounds. You can inspect the parent run in MLflow UI to see
the refinement progress as kappa improves and disagreements decrease across
rounds.

Do not use PMI in this loop. PMI runs after large-scale generation and consensus
validation.
```
