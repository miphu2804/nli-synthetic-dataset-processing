# Validator Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MCP validation phase that reads generated NLI samples in masked batches, accepts independent validator verdicts, and finalizes one validation results CSV.

**Architecture:** Mirror the existing generation runtime instead of adding a new framework. Keep label masking at claim time, compare validator labels only at submit time, and expose the validator rubric as `skill://validator` so any external validator can plug in through MCP.

**Tech Stack:** Python 3.11, FastAPI, FastMCP, Pydantic v2, pandas, unittest, uv.

---

### Task 1: Validator Schemas

**Files:**
- Create: `src/schemas/validation_runtime_schema.py`
- Modify: `src/schemas/__init__.py`
- Test: `tests/test_validation_run_service.py`

- [ ] Write failing schema/service-facing tests for masked sample shape, verdict acceptance counts, and finalize response paths.
- [ ] Add Pydantic models:
  - `MaskedValidationRow`: `source_uid`, `premise`, `hypothesis`, `masked_label`.
  - `ValidatorVerdict`: `source_uid`, `predicted_label`, `reason`.
  - `ValidationRunManifest`, `ValidationRunListItem`, progress/finalize/submit response models.
- [ ] Export models from `src/schemas/__init__.py`.
- [ ] Verify with `uv run python -m unittest tests.test_validation_run_service`.

### Task 2: Validator Service

**Files:**
- Create: `src/services/validation_run_service.py`
- Modify: `src/services/__init__.py`
- Test: `tests/test_validation_run_service.py`

- [ ] Write failing tests for:
  - starting a validation run from CSV with `uid` or `source_uid`;
  - claiming rows without exposing the original label;
  - submit rejecting source_uid outside the claim;
  - submit marking whether each predicted label matches the expected label;
  - finalize writing one `validation_results.csv` file.
- [ ] Implement `ValidationRunService` with direct helpers matching `GenerationRunService` style:
  - `start_validation_run`;
  - `claim_next_validation_batch`;
  - `submit_validation_result`;
  - `get_validation_progress`;
  - `release_validation_batch_claim`;
  - `finalize_validation_run`;
  - `verify_validation_progress_log`;
  - `list_validation_runs`.
- [ ] Use `.pipeline/validation-runs/{run_id}` so validation state does not collide with generation state.
- [ ] Use `ProgressTrackingService` by giving it a validation-specific pipeline root.
- [ ] Verify with targeted unittest.

### Task 3: MCP Provider and App Wiring

**Files:**
- Create: `src/providers/validation_provider.py`
- Modify: `src/providers/__init__.py`
- Modify: `src/main.py`
- Test: `tests/test_validation_provider.py`

- [ ] Write failing MCP tests that register validation tools and call a start/claim/submit/finalize round trip.
- [ ] Register tools:
  - `start_validation_run`;
  - `claim_next_validation_batch`;
  - `submit_validation_result`;
  - `get_validation_progress`;
  - `release_validation_batch_claim`;
  - `finalize_validation_run`;
  - `verify_validation_progress_log`;
  - `list_validation_runs`.
- [ ] Wire `register_validation_tools(mcp)` in `src/main.py`.
- [ ] Verify tool schemas do not expose `self` and claimed rows expose `masked_label`, not `label`.

### Task 4: Validator Rubric Skill

**Files:**
- Create: `skills/validator.md`
- Modify: `README.md`
- Test: `tests/test_skill_service.py`

- [ ] Write failing test that `SkillService().get_skill("validator")` returns the validator rubric.
- [ ] Add `skill://validator` with:
  - NLI grading rules used by the current run;
  - instruction that the original label is masked and must not be inferred from metadata;
  - required JSON verdict format;
  - `reason` as the full explanation for the chosen label.
- [ ] Update README resource map and state machine to include validation after generation.

### Task 5: Verification and Handoff

**Files:**
- Modify: `.gitignore` only if needed.
- Modify: `docs/handoff.md`

- [ ] Run `uv run python -m unittest`.
- [ ] Run `uv run python -m py_compile` on changed Python files.
- [ ] Append a short local handoff entry with edits, assumptions, caveats, and next follow-up.
- [ ] Check `git status --short`.

## Reflection

- This keeps validation as runtime orchestration, matching the existing generator contract and avoiding model-provider code that was not requested.
- The validator can be any MCP client/agent/model because the server only supplies masked samples and records verdicts.
- Consensus across multiple validators belongs in the offline aggregation flow; this runtime records one validator output and trusted expected-label comparison at a time.

## Unresolved Questions

- Should the project later support three-way labels (`entailment`, `contradiction`, `neutral`) and paper-style binary labels in the same validation run?
