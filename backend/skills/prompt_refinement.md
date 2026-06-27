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
- inspect disagreements, propose the smallest responsible instruction change,
  and decide whether to request lock confirmation.

Each subagent is a stateless validator. Give it only `source_uid`, `premise`,
`hypothesis`, the 3-class rubric, and its output path identity. It must return
`source_uid,predicted_label,reason` for every assigned row.

Subagent rules:

- Do not read the labeled calibration file or expected label.
- Do not see another subagent's verdicts or reasons.
- Do not call MCP tools, edit instructions, write runtime state, or decide to
  lock.
- Do not impersonate a different model. Three subagents using one model are not
  three-model agreement.

If a subagent returns invalid schema or UID coverage, retry only that model once.
If it still fails, stop the round and report the blocker. Do not duplicate a
successful model's verdict file.

## Flow

1. Load the generation policy being calibrated and generate the calibration
   rows for the frozen source UID set. Use `skill://generator_plain` for plain
   ANLI-style translation runs and `skill://generator_adversarial` for
   controlled adversarial runs. If only validator instructions changed, reuse
   the same generated calibration file. If generator instructions changed,
   regenerate the same source UID set and record the new round hash.
2. Load `skill://validator` and dispatch exactly three independent model
   subagents to judge the same generated rows without seeing expected labels.
3. Validate the three returned verdict sets and save one verdict file per model
   in a dedicated round directory.
4. The main agent calls `evaluate_prompt_refinement_round` with the verdict
   directory, generated labeled calibration file path, round number, change
   summary, MLflow tracking URI, and optionally `session_id` to group all rounds
   of one calibration session together. Pass `generator_skill_name` as
   `generator_plain`, `generator_adversarial`, or the legacy `generator` so
   MLflow versions the policy that produced the calibration rows.
5. Follow the returned decision:

| Decision | Action |
|----------|--------|
| `refine_prompt` | Build the evidence pack, collect two editor proposals, choose the responsible instruction change, then repeat on the same calibration dataset. |
| `eligible_to_lock` | Report the candidate versions. Continue refining or request explicit lock confirmation. |

Fleiss' kappa below `0.85` means refine. Kappa at least `0.85` is eligible to
lock; it does not lock automatically. To lock an eligible round, call
`confirm_prompt_lock(lock_run_id=<mlflow_run_id>)` where mlflow_run_id is the
run ID of the eligible round you wish to lock.

Locking uses the exact prompt versions from the evaluated round, not whichever
instructions are current later. This means later edits do not change what an
approved lock references.

When a generator change regenerates calibration text, treat the result as a new
round with the same source UID set but different item content. Report the new
hash and do not present the kappa delta as a strict same-item comparison.

## Round Integrity (prompt provenance)

Within a single round, the chosen generator policy instructions and validator
rubric must stay byte-identical from the moment you dispatch the validator
subagents until `evaluate_prompt_refinement_round` returns. Kappa is computed
on verdicts produced by the instructions as they were at dispatch time, while
the tool registers the instructions visible to the MCP server at evaluation
time. Editing either instruction mid-round makes the registered MLflow prompt
version diverge from the prompts that actually produced the verdicts.

If you need to change a prompt, finish or abandon the current round first, then
run a new round. Do not keep parallel hand-managed prompt-version copies:
MLflow's Prompt Registry already versions every generator and validator prompt
on each evaluation (`nli-generator` / `nli-validator` vN), so manual copies are
redundant and provide no extra provenance safety.

## Failed-Round Review Workflow

When `evaluate_prompt_refinement_round` returns `decision=refine_prompt`, the
backend has already logged the round evidence to MLflow, including
`disagreement_rows.csv`, `prompt_bundle.json`, the calibration manifest, and the
three verdict files. The harness owns the next step: inspect those artifacts,
decide whether a prompt change is justified, and start a new round if needed.

Do not ask validator subagents to revise instructions. If the harness uses
editor subagents, run them with the static editor templates in
`docs/*/template/prompt-refinement-editor-*.md` and give them only the evidence
the harness intentionally exports from the MLflow round. The backend does not
create editor prompts, spawn agents, call model APIs, edit instructions, write
local review packs, or run the next round.

Run exactly two editor subagents:

- validator-rubric reviewer;
- generator-policy reviewer.

Each editor returns only a proposal, never file edits or MCP calls:

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

If an editor thinks both prompts might be implicated, it should explain the
ambiguity and still return `no_change`. Editors do not return `both`.

Reject a proposal if it:

- relies on hidden labels as validator-facing evidence;
- uses PMI as prompt-refinement evidence;
- treats one model as ground truth;
- changes broad policy without source_uid evidence;
- would expose labels or peer verdicts to validator subagents;
- asks editors to call MCP tools or edit files;
- cannot be summarized in one small `change_summary`;
- tries to weaken the rubric to excuse bad calibration rows.

Selection rules:

- Prefer `no_change` and stop if both proposals point to calibration-row
  problems.
- Prefer the smallest single-target proposal.
- Prefer generator-policy changes when rows are semantically ambiguous,
  unnatural, source-drifting, or label-drifting.
- Prefer validator-rubric changes when generated rows are sound but class
  boundaries are unclear.
- If evidence is mixed, stop and ask the operator.

After choosing one proposal, apply one instruction change, preserve the same
source UID set, rerun the three validator subagents, and call
`evaluate_prompt_refinement_round` again. Stop when the latest decision is
`eligible_to_lock`, when `max_rounds` is reached in the active harness, when no
valid proposal remains, or when an external blocker prevents another round.

## Choose What to Edit

- Change the chosen generator policy instructions when disagreements come from
  ambiguous, unnatural, or logically incorrect generated hypotheses.
- Change the validator rubric when disagreements come from unclear distinctions
  between entailment, neutral, and contradiction.
- Change both only when the disagreement evidence supports both causes.
- Change the smallest instruction needed and describe it in `change_summary`.

Do not use PMI as a prompt-refinement trigger. PMI belongs to post-generation
artifact analysis and paraphrasing.

## Session ID and Trend Tracking

Pass `session_id` (a string identifying the calibration session) to
`evaluate_prompt_refinement_round` to create a parent run that aggregates all
rounds for that session. Each round becomes a child run, and kappa and
disagreement count are logged as step metrics on the parent run. This enables
MLflow to display a trend line showing kappa and disagreement improvement across
refinement rounds. Without `session_id`, each round is logged as a standalone
run (backward compatible).

A session is anchored to the calibration source-UID set of its first round. A
later round under the same `session_id` whose UID set differs is rejected, so the
trend never mixes incomparable item sets; use a new `session_id` for a different
calibration set. Confirming a lock finalizes the session's parent run.

## Report

Return the proposed or changed instructions, kappa, decision, calibration
dataset hash, generator and validator prompt versions, model identifiers,
bundle ID, and MLflow run ID. Retrieve `disagreement_rows.csv` from
that run's MLflow Artifacts tab when refinement is required. If `session_id`
was provided, view the trend on the parent `calibration-session-*` run in
MLflow UI: inspect `fleiss_kappa` and `n_disagreements` metrics over steps to
see refinement progress.
