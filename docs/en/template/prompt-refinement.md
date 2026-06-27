# Prompt Refinement Orchestration Template

Use this prompt when Codex is connected to MCP server `nli-tools` and the
operator has already started the required services.

```text
You are the main agent connected to MCP server `nli-tools`.

Goal:
Run one prompt-refinement round for the selected NLI generation policy and
validator rubric.

Inputs:
- calibration_source: <FIXED_LABELED_DATASET_OR_SLICE>
- sample_count: <N>
- generator_skill_name: <generator_plain_OR_generator_adversarial_OR_generator>
- output_root: data/prompt-refinement/<SESSION_ID_OR_DATASET_ID>
- tracking_uri: <MLFLOW_TRACKING_URI>
- experiment_name: <MLFLOW_EXPERIMENT_NAME>
- session_id: <OPTIONAL_SESSION_ID>
- round_number: <N>
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>
- max_rounds: <N>

Required MCP resources:
- skill://instructor
- skill://prompt_refinement
- skill://validator
- skill://<generator_skill_name>

Task:
1. Read only the required MCP resources and the provided calibration_source.
2. Freeze the selected source_uid set for this session.
3. Create output_root/round-<NN>/calibration.csv with:
   source_uid,premise,hypothesis,label
4. Give each validator only masked rows:
   source_uid,premise,hypothesis
5. Run exactly three independent validator models/subagents.
   If three independent models are unavailable, stop and report a blocker.
6. Save one verdict file per model under:
   output_root/round-<NN>/verdicts/<model-id>.csv

Verdict schema:
source_uid,predicted_label,reason

Reject a verdict set with missing UID, duplicate UID, invalid label, blank
reason, or incomplete UID coverage. Retry only the failed model once.

Then call:
evaluate_prompt_refinement_round(
  verdicts_dir="output_root/round-<NN>/verdicts",
  calibration_input="output_root/round-<NN>/calibration.csv",
  round_number=<NN>,
  change_summary="<PROMPT_CHANGES_TESTED_THIS_ROUND>",
  tracking_uri="<MLFLOW_TRACKING_URI>",
  experiment_name="<MLFLOW_EXPERIMENT_NAME>",
  session_id="<OPTIONAL_SESSION_ID>",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Auto-refine after a failed round:
1. If decision=eligible_to_lock, stop and report. Do not lock without approval.
2. If decision=refine_prompt and round_number < max_rounds, inspect the MLflow
   artifacts for the evaluated run, especially disagreement_rows.csv,
   prompt_bundle.json, the calibration manifest, and the verdict files.
3. Spawn exactly two editor subagents with the static editor templates if a
   review is needed:
   - validator-rubric reviewer
   - generator-policy reviewer
4. Give both editors only the evidence intentionally exported from the evaluated
   MLflow round. Editors return proposals only using:
   target: generator | validator | no_change
   evidence_uids: [...]
   diagnosis: ...
   proposed_patch: ...
   expected_effect: ...
   risk: ...
   change_summary: ...
6. Reject a proposal if it relies on hidden labels as validator-facing
   evidence, uses PMI, treats one model as ground truth, changes broad policy
   without source_uid evidence, leaks labels or peer verdicts to validator
   subagents, asks editors to call MCP or edit files, cannot fit one small
   change_summary, or tries to weaken the rubric to excuse bad calibration
   rows.
7. Selection rules:
   - Prefer no_change and stop if both proposals point to calibration-row
     problems.
   - Prefer the smallest single-target proposal.
   - Prefer generator-policy changes for semantic ambiguity, unnatural
     Vietnamese, source-fidelity drift, or label drift.
   - Prefer validator-rubric changes when generated rows are sound but class
     boundaries are unclear.
   - If evidence is mixed, stop and ask the operator.
8. Apply one instruction change, create round-<NN+1>, preserve the same
   source_uid set, rerun the three validator models, and call
   evaluate_prompt_refinement_round again.
9. Stop on eligible_to_lock, max_rounds, blocker, or no valid proposal.

Rules:
- Do not read hidden labels outside calibration_source preparation.
- Validator subagents remain blind. Do not expose labels, expected label
  values, or peer verdicts to them.
- Editor subagents are post-failure reviewers. They may inspect labels inside
  the evidence pack only to diagnose the failed round and return proposals.
- Validator subagents do not call MCP tools or write runtime state.
- Editor subagents do not call MCP tools, edit files, write runtime state, run
  evaluation, or decide lock status.
- Do not inspect unrelated repository files.
- Do not edit generator or validator instructions during a round.
- Do not use PMI in this loop.
- Do not call confirm_prompt_lock unless explicitly approved.
- If MCP or MLflow is unavailable, report the blocker; do not start servers.

Report:
- verdict file paths
- kappa and decision
- disagreement artifact path if any
- generator and validator prompt versions
- bundle ID
- MLflow run ID
- blockers or unresolved questions
```
