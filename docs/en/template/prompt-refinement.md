# Prompt Refinement Orchestration Template

Use this prompt when Codex is already connected to MCP server `nli-tools`.

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
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>

Skills to load from the connected `nli-tools` skill lookup:
- instructor
- prompt_refinement
- validator
- <generator_skill_name>

Task:
1. Read only the required skills and the provided calibration_source.
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
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Decision handling:
1. If decision=accepted, stop and report the calibration result.
2. If decision=needs_prompt_update, stop automatic execution. Inspect the logged
   disagreement_rows.csv, prompt snapshots, verdict files, and calibration rows.
3. Report the rejected sample count, disagreement evidence, and the smallest
   evidence-backed next step for user approval. Do not edit prompts unless the
   user explicitly approves that follow-up.

Rules:
- Do not read hidden labels outside calibration_source preparation.
- Validator subagents remain blind. Do not expose labels, expected label
  values, or peer verdicts to them.
- Validator subagents do not call MCP tools or write runtime state.
- Do not inspect unrelated repository files.
- Do not edit generator or validator instructions during calibration.
- Do not use PMI in this loop.
- Do not ask the backend to propose prompt edits; the main agent owns evidence
  review and user-facing recommendations.
- Do not register prompt versions, promote aliases, or lock prompts.
- If required skills, tools, or three independent validator executions are
  unavailable, report the blocker.

Report:
- verdict file paths
- kappa and decision
- rejected sample count
- disagreement_rows.csv
- agent-owned next step or blocker
- bundle ID
- MLflow run ID
- blockers or unresolved questions
```
