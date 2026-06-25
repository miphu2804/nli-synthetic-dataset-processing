# Feature Plan: Prompt Refinement Editor Candidates

## Branch

`feature/prompt-refinement-editor-candidates`

## Objective

Add a controlled agent-orchestration workflow for prompt refinement after a
failed Fleiss kappa round.

The feature does **not** make backend or MLflow auto-edit prompts. It gives the
main agent a clear, repeatable procedure:

```text
round fails kappa
  -> main agent builds evidence pack
  -> two editor subagents propose candidate instruction changes
  -> main agent chooses the smallest evidence-backed proposal
  -> main agent applies one change and runs the next round
```

## Current State

Existing backend behavior:

- `evaluate_prompt_refinement_round` evaluates one round.
- It logs kappa, disagreement rows, verdict files, and prompt versions to
  MLflow.
- It returns `decision=refine_prompt` or `decision=eligible_to_lock`.
- It does not spawn subagents, edit prompts, run loops, or lock automatically.

Existing prompt registry behavior:

- MLflow Prompt Registry can show `nli-generator` and `nli-validator` versions.
- `candidate` and `locked` aliases are visible in the UI.
- Experiment runs show metrics and artifacts, but no traces. This is expected
  because this workflow does not use MLflow tracing.

## Design Decision

Keep the refinement loop **harness-owned**, with one focused backend MCP helper.

Do not add backend loop tooling. The backend cannot reliably spawn three real
validator models or editor agents. That orchestration belongs to the main
agent/harness. The backend can, however, deterministically prepare the failed
round evidence pack that editor agents inspect.

Responsibilities:

| Actor | Responsibility |
|---|---|
| Validator subagents | Blind label prediction only: `source_uid,predicted_label,reason`. |
| Editor subagents | Non-blind proposal review after kappa fails. They see evidence, return proposals only. |
| Main agent | Calls MCP helpers, spawns editors from returned payloads, rejects unsafe proposals, applies one change, reruns validators, calls MCP evaluation, asks before lock. |
| MCP backend | One-round deterministic evaluation/logging through `evaluate_prompt_refinement_round`; local evidence-pack creation through `prepare_prompt_refinement_evidence_pack`; editor task payload creation through `prepare_prompt_refinement_editor_tasks`. |
| MLflow | Tracks runs, prompt versions, metrics, artifacts, aliases. |
| Git | Publishes final approved prompt/template changes for teammates. |

## In Scope For This Branch

- Add editor templates for two roles:
  - validator-rubric reviewer;
  - generator-policy reviewer.
- Extend prompt-refinement orchestration templates with:
  - `max_rounds`;
  - evidence-pack convention;
  - `prepare_prompt_refinement_evidence_pack`;
  - `prepare_prompt_refinement_editor_tasks`;
  - two editor subagents;
  - proposal selection rules;
  - next-round rerun procedure;
  - no auto-lock rule.
- Add MCP/backend helper `prepare_prompt_refinement_evidence_pack` to write
  deterministic failed-round editor inputs from calibration, verdicts, and
  current prompt instructions.
- Add MCP/backend helper `prepare_prompt_refinement_editor_tasks` to write the
  two concrete editor-subagent task payload files for the orchestrator.
- Keep docs free of:
  - local absolute paths;
  - repo-location prompts like "you are in repo";
  - server-start commands;
  - instructions to inspect unrelated repository files.
- Keep `docs/PROGRESS.md` trimmed to 10 entries.

## Out Of Scope

- No `run_prompt_refinement_loop` MCP tool.
- No backend-spawned subagents.
- No backend prompt editing.
- No MLflow trace logging.
- No automatic `confirm_prompt_lock`.
- No PMI use inside prompt refinement.
- No prompt-bundle export/promote tooling in this branch.

## Files

Created:

- `docs/en/template/prompt-refinement-editor-validator-rubric.md`
- `docs/en/template/prompt-refinement-editor-generator-policy.md`
- `docs/vi/template/prompt-refinement-editor-validator-rubric.md`
- `docs/vi/template/prompt-refinement-editor-generator-policy.md`
- `docs/superpowers/plans/prompt-refinement-editor-candidates.md`

Modified:

- `docs/en/template/prompt-refinement.md`
- `docs/vi/template/prompt-refinement.md`
- `docs/en/flow/validator.md`
- `docs/vi/flow/validator.md`
- `docs/PROGRESS.md`
- `README.md`
- `README.vi.md`
- `backend/skills/instructor.md`
- `backend/skills/prompt_refinement.md`
- `backend/src/services/prompt_refinement_service.py`
- `backend/src/providers/validation_provider.py`
- `backend/src/schemas/validation_runtime_schema.py`
- `backend/tests/test_prompt_refinement_service.py`
- `backend/tests/test_validation_provider.py`
- `backend/tests/test_skill_service.py`

Known unrelated working-tree item:

- `backend/data/validation/validation_masked.csv` is deleted in the worktree
  from earlier state. Do not touch it in this feature unless explicitly asked.

## Evidence Pack Contract

When a round returns `decision=refine_prompt`, the main agent creates:

```text
output_root/round-<NN>/evidence/
  disagreement_rows.csv
  disagreement_calibration_rows.csv
  round_summary.json
  current_generator_instructions.md
  current_validator_instructions.md
```

The pack includes:

- disagreement rows;
- calibration rows for disagreement UIDs;
- summary of all three verdict files;
- kappa, decision, label distribution, disagreement count;
- generator policy instructions used for the failed round;
- validator rubric used for the failed round;
- `generator_skill_name`, prompt versions, dataset hash.

Editor agents may inspect only this pack. They must not inspect unrelated repo
files.

## Editor Roles

Use exactly two editor roles.

### Validator-Rubric Reviewer

Purpose:

- Identify unclear entailment / neutral / contradiction boundaries.
- Propose validator rubric changes only.

Return `no_change` if evidence points to:

- generated text ambiguity;
- label drift;
- bad calibration row;
- generator policy issue.

### Generator-Policy Reviewer

Purpose:

- Identify generated hypothesis ambiguity;
- detect unnatural Vietnamese;
- detect semantic/source-fidelity drift;
- detect label drift.

Propose generator policy changes only.

Return `no_change` if evidence points to:

- validator rubric ambiguity;
- genuinely ambiguous source row;
- bad calibration row requiring operator decision.

## Editor Proposal Schema

Each editor returns exactly:

```yaml
target: generator | validator | no_change
evidence_uids:
  - "<source_uid>"
diagnosis: "<why the failed round disagreed>"
proposed_patch: "<minimal instruction change or no_change>"
expected_effect: "<how this should improve agreement>"
risk: "<possible overfit or label drift risk>"
change_summary: "<short summary for evaluate_prompt_refinement_round>"
```

No `both` target for editor agents. If both prompts seem implicated, the editor
should explain the ambiguity and return `no_change`; the main agent decides
whether to stop or run a separate focused round.

## Main Agent Selection Rules

Reject a proposal if it:

- relies on hidden labels as validator-facing evidence;
- uses PMI as prompt-refinement evidence;
- treats one model as ground truth;
- changes broad policy without source_uid evidence;
- would expose labels or other model outputs to validator subagents;
- requires editor agents to call MCP or edit files;
- cannot be summarized in one small `change_summary`;
- tries to fix bad calibration rows by weakening the rubric.

Selection:

1. Prefer `no_change` + stop if both proposals show calibration row problems.
2. Prefer the smallest single-target proposal.
3. Prefer generator-policy change when rows are semantically ambiguous or
   label-drifting.
4. Prefer validator-rubric change when generated rows are sound but validators
   disagree on class boundaries.
5. If evidence is mixed, stop and ask the operator.

## Auto-Refine Loop

Inputs:

```text
calibration_source
sample_count
generator_skill_name
output_root
tracking_uri
experiment_name
session_id
validator_models
max_rounds
```

Loop:

```text
if no prior round:
  create round-01
  run three blind validator subagents
  call evaluate_prompt_refinement_round

if latest decision=eligible_to_lock:
  report kappa, prompt versions, run ID
  ask operator before confirm_prompt_lock

if latest decision=refine_prompt and round_number < max_rounds:
  call prepare_prompt_refinement_evidence_pack
  call prepare_prompt_refinement_editor_tasks
  spawn validator-rubric editor from returned task payload
  spawn generator-policy editor from returned task payload
  collect proposals
  reject unsafe/broad proposals
  choose one minimal proposal
  apply one instruction change
  create round-N+1 using same source_uid set
  rerun three blind validator subagents
  call evaluate_prompt_refinement_round
  repeat

if max_rounds reached or no valid proposal:
  stop and report blocker
```

## Prompt Persistence Model

Use MLflow for exploration and Git for final publication.

MLflow stores:

- prompt versions;
- candidate/locked aliases;
- kappa metrics;
- disagreement artifacts;
- verdict files;
- bundle metadata.

Git stores:

- final approved skills/templates;
- stable workflow docs;
- code needed for teammates.

Do not commit every prompt candidate. Commit only the final approved prompt
changes and stable workflow docs.

## Future Work, Separate Branches

These are deliberately outside this branch:

### Prompt Snapshot Support

Possible future MCP extension:

```text
evaluate_prompt_refinement_round(..., prompt_snapshot_dir=<optional_dir>)
```

Use only if we need true candidate grid search without mutating canonical prompt
files.

### MLflow Prompt URI Evaluation

Possible future MCP extension:

```text
evaluate_prompt_refinement_round(
  ...,
  generator_prompt_uri=<optional>,
  validator_prompt_uri=<optional>
)
```

Use only if MLflow Prompt Registry becomes the source of truth for candidate
prompt text during refinement.

### Calibrated Prompt Bundle Export

Possible future tools:

```text
export_locked_prompt_bundle(lock_run_id, output_dir)
promote_calibrated_prompt_bundle(bundle_dir, generator_skill_name)
```

Use only after a prompt candidate is approved. Exporting should be explicit;
never auto-promote into repo skills just because kappa passes.

## Acceptance Criteria

- Two editor templates exist in EN and VI.
- Main prompt-refinement templates describe:
  - evidence pack;
  - `prepare_prompt_refinement_evidence_pack`;
  - `prepare_prompt_refinement_editor_tasks`;
  - two editor roles;
  - proposal-only editors;
  - next-round loop;
  - same `source_uid` set;
  - no auto-lock;
  - no PMI.
- Editor templates prohibit:
  - MCP calls;
  - file edits;
  - runtime writes;
  - evaluation calls;
  - lock decisions.
- Templates contain no local absolute paths or server-start commands.
- MCP exposes `prepare_prompt_refinement_evidence_pack`.
- MCP exposes `prepare_prompt_refinement_editor_tasks`.
- Evidence-pack service writes disagreement rows, disagreement calibration rows,
  round summary, and current instruction snapshots.
- Editor-task service writes one validator-rubric reviewer payload and one
  generator-policy reviewer payload for the orchestrator.
- Existing targeted tests pass.
- `docs/PROGRESS.md` has at most 10 entries.

## Verification

Run:

```bash
cd backend
uv run pytest tests/test_skill_service.py tests/test_validation_provider.py tests/test_prompt_refinement_service.py -q
```

Leakage scan:

```bash
rg -n '(/Users/|Bạn đang ở repo|You are in repo|uv run mlflow|mlflow server|backend/skills/|backend/src/)' \
  docs/en/template docs/vi/template
```

Progress log count:

```bash
rg -n '^### ' docs/PROGRESS.md
```

## Rollback

To revert only this feature's template additions:

- remove the four `prompt-refinement-editor-*` templates;
- revert auto-refine sections in EN/VI `prompt-refinement.md`;
- remove `prepare_prompt_refinement_evidence_pack` and
  `prepare_prompt_refinement_editor_tasks` provider/service/schema/tests;
- remove this plan file;
- remove the latest `PromptRefinement` progress entry.

Do not restore or delete unrelated data files during rollback.

## Open Questions

- Should auto-refine apply prompt edits automatically, or require operator
  approval before each edit? Current template allows main-agent apply, but stops
  when evidence is ambiguous.
- Should final approved MLflow prompt versions be exported to a calibrated
  bundle folder before copying into `backend/skills`? This is deferred.
- Should team MLflow move from local server to cloud tracking? Supported by
  `tracking_uri`, but deployment is outside this branch.
