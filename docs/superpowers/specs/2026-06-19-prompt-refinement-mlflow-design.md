# Prompt Refinement with Local MLflow

## Goal

Add an optional, agent-operated prompt-refinement loop before large-scale
generation. The loop versions the current generator and validator skills,
computes Fleiss' kappa from exactly three calibration verdict files, records the
round in a local MLflow server, and tells the agent whether to refine or lock the
prompt bundle.

This feature does not start MLflow with the backend. Operators run MLflow only
when refinement is needed.

## Operator Flow

Start the existing backend/MCP server:

```bash
cd backend
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Start local MLflow separately when running calibration:

```bash
cd backend
mkdir -p .mlflow/artifacts
uv run mlflow server \
  --backend-store-uri "sqlite:///$PWD/.mlflow/mlflow.db" \
  --default-artifact-root "file://$PWD/.mlflow/artifacts" \
  --host 127.0.0.1 \
  --port 5000
```

MLflow UI:

```text
http://127.0.0.1:5000
```

The agent then reads `skill://prompt_refinement` and executes:

```text
fixed calibration sample
  -> generate hypotheses with current generator skill
  -> run exactly three independent validators
  -> save source_uid,predicted_label,reason per model
  -> call evaluate_prompt_refinement_round
  -> kappa < 0.85: inspect disagreements, edit responsible skill, repeat
  -> kappa >= 0.85: prompt bundle is eligible to lock
  -> agent may continue refinement or explicitly confirm the lock
```

PMI and paraphrasing are not part of this loop.

## Components

### `skill://prompt_refinement`

Create `backend/skills/prompt_refinement.md`.

The skill:

- requires a fixed calibration dataset across rounds;
- requires exactly three independent verdict files;
- distinguishes generation ambiguity from labeling-rubric ambiguity;
- edits `backend/skills/generator.md` when generated hypotheses are unclear or
  logically wrong;
- edits `backend/skills/validator.md` when the three-class rubric or labeling
  instructions cause disagreement;
- may edit both only when evidence supports both changes;
- calls the MCP evaluation tool after every round;
- treats kappa of at least `0.85` as eligible to lock, not an automatic stop;
- reports changed prompt files and the MLflow run/prompt versions.

The skill must not claim that it can produce three model verdicts unless the
active harness actually provides the required model execution paths.

### MCP tool: `evaluate_prompt_refinement_round`

Add a thin tool to the validation provider. It delegates to a focused service;
the provider contains no kappa or MLflow business logic.

Inputs:

```text
verdicts_dir: directory containing exactly three valid verdict CSV/parquet files
calibration_input: fixed labeled calibration dataset used for this round
round_number: positive integer
change_summary: concise description of changes tested in this round
confirm_lock: set true only when the agent/operator chooses to lock an eligible round
tracking_uri: MLflow tracking server, default http://127.0.0.1:5000
experiment_name: default nli-prompt-calibration
```

The tool reads prompt content from the current:

```text
skills/generator.md
skills/validator.md
```

It does not accept arbitrary prompt text from the caller.

Output:

```json
{
  "kappa": 0.87,
  "threshold": 0.85,
  "decision": "eligible_to_lock",
  "n_items": 50,
  "n_raters": 3,
  "models": ["gpt4o", "deepseek", "llama"],
  "generator_prompt_version": 3,
  "validator_prompt_version": 2,
  "calibration_dataset_sha256": "a1b2c3d4...",
  "bundle_id": "round-03-a1b2c3d4",
  "mlflow_run_id": "...",
  "mlflow_run_url": "http://127.0.0.1:5000/#/experiments/..."
}
```

Allowed decisions:

```text
refine_prompt
eligible_to_lock
lock_prompt
```

### Refinement service

Create a small service responsible for:

1. validating paths and round metadata;
2. reusing `compute_fleiss_kappa()` rather than duplicating the statistic;
3. hashing the calibration dataset;
4. registering the current generator and validator skill snapshots as MLflow
   prompt versions;
5. creating one MLflow experiment run per round;
6. logging parameters, metrics, tags, and artifacts;
7. assigning `candidate` aliases each round and `locked` aliases only when
   `kappa >= 0.85` and `confirm_lock=true`;
8. returning a structured result to the MCP provider.

No automatic model calls and no automatic prompt rewriting belong in this
service.

## MLflow Record

Prompt Registry names:

```text
nli-generator
nli-validator
```

Each calibration run logs:

Parameters:

```text
round_number
generator_prompt_uri
validator_prompt_uri
calibration_dataset_sha256
sample_count
model_names
git_commit
```

Metrics:

```text
fleiss_kappa
entailment_proportion
neutral_proportion
contradiction_proportion
```

Tags:

```text
decision
change_summary
bundle_id
```

Artifacts:

```text
three verdict files
calibration dataset manifest
prompt_bundle.json
disagreement_rows.csv
```

`prompt_bundle.json` is the immutable link between the two prompt versions and
the calibration run. Individual prompt aliases alone are not treated as the
bundle source of truth.

## Failure Behavior

- MLflow unavailable: fail the MCP call without changing aliases.
- Wrong verdict-file count or schema: fail before registering prompt versions.
- Verdict UID mismatch: fail before logging a successful round.
- Calibration dataset changed between rounds: the tool still records the hash,
  but the skill must stop and report that cross-round kappa comparison is not
  valid.
- Kappa below threshold: log the round with `refine_prompt`; do not assign
  `locked`.
- Kappa at or above threshold without explicit confirmation: log
  `eligible_to_lock`; keep only the `candidate` aliases.
- `confirm_lock=true` below threshold: reject before changing aliases.
- Partial MLflow write after run creation: mark that run failed, raise the
  MLflow error, and never report the bundle as locked.

## Repository Changes

Create:

- `backend/skills/prompt_refinement.md`
- `backend/src/services/prompt_refinement_service.py`
- `backend/tests/test_prompt_refinement_service.py`

Modify:

- `backend/src/providers/validation_provider.py`
- `backend/src/providers/__init__.py` only if a separate provider is required;
  prefer keeping the tool in the validation provider.
- `backend/src/schemas/validation_runtime_schema.py`
- `backend/src/services/__init__.py`
- `backend/src/main.py` only if registration changes are required.
- `backend/pyproject.toml`
- `backend/uv.lock`
- `.gitignore`
- `backend/skills/instructor.md`
- `README.md`
- `README.vi.md`
- `docs/en/flow/validator.md`
- `docs/vi/flow/validator.md`
- `docs/en/template/validator.md`
- `docs/vi/template/validator.md`
- `docs/PROGRESS.md`

## Verification

- Service tests use a temporary local SQLite MLflow store and do not require a
  running server.
- Existing backend suite remains green.
- `uv run pre-commit run --all-files` passes.
- MCP tool list contains `evaluate_prompt_refinement_round`.
- A local smoke round appears in MLflow UI with both prompt versions, kappa,
  prompt bundle, verdict artifacts, and the correct decision.
- Documentation keeps these distinctions explicit:
  - low kappa refines prompt setup;
  - high PMI paraphrases hypotheses;
  - calibration precedes large-scale generation;
  - three-model execution remains an agent/harness responsibility.

## Non-goals

- Starting MLflow automatically with FastAPI.
- Calling LLM providers from backend code.
- Automatically generating or rewriting skill content in Python.
- Adding prompt editing through the MLflow UI.
- Exposing aggregate, PMI, or paraphrase as MCP tools in this feature.
- Implementing post-paraphrase semantic promotion.
