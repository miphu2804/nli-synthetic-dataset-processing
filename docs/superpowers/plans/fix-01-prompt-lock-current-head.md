# Fix 01 — Prompt Lock Current Head

Proposed branch: `fix/prompt-lock-current-head`

Status: fixed locally on this branch. The local MLflow SQLite registry now has
`locked -> v1` for both prompt names, and run
`27b4cd6625b549738578c2ee42e9a63f` has `lock_confirmed=true`.

## Problem

Prompt refinement has one local MLflow round with `decision=eligible_to_lock`
and Fleiss' kappa above threshold, but the prompt bundle is not confirmed as
`locked`. The current local MLflow DB shows only `candidate` aliases for
`nli-generator` and `nli-validator`.

There is also provenance drift: the MLflow round was logged from commit
`8d36a05`, while the repo head during the monitor run was `8243580`. Locking
that old round may be acceptable only if the user intentionally wants to lock
the evaluated prompt versions rather than rerun calibration on current HEAD.

## Verified Evidence

- `backend/.mlflow/mlflow.db` contains run `27b4cd6625b549738578c2ee42e9a63f`.
- Run status: `FINISHED`.
- Run decision tag: `eligible_to_lock`.
- Metric: `fleiss_kappa=0.9591503267973857`.
- Prompt params: `prompts:/nli-generator/1`, `prompts:/nli-validator/1`.
- `registered_model_aliases` contains `candidate` only; no `locked` alias.
- `uv run python -m src.cli kappa --verdicts-dir outputs/prompt-refinement/round-01/verdicts`
  reports `Kappa 0.9592`, `Items 50`, `Raters 3`.

## Scope

- Decide whether to confirm the existing eligible round or rerun calibration on
  current HEAD first.
- If confirming, call the existing `confirm_prompt_lock` tool or service path
  against the exact MLflow run id.
- If rerunning, keep the same calibration UID set unless there is a deliberate
  reason to start a new calibration session.

## Out Of Scope

- Do not change generator or validator prompt content in this branch unless the
  decision is to rerun calibration after prompt edits.
- Do not touch validation aggregation, PMI, paraphrase, or split logic.

## Acceptance Criteria

- Prompt registry has `locked` aliases for both `nli-generator` and
  `nli-validator`.
- The locked versions match the evaluated bundle intended for lock.
- The MLflow run has `lock_confirmed=true`, or the report clearly explains why
  lock was intentionally deferred.
- Backend tests still pass.

## Verification

```bash
cd backend
uv run pytest -q
uv run python - <<'PY'
from pathlib import Path
from mlflow import MlflowClient
tracking_uri = f"sqlite:///{Path('.mlflow/mlflow.db').resolve()}"
client = MlflowClient(
    tracking_uri=tracking_uri,
    registry_uri=tracking_uri,
)
for name in ("nli-generator", "nli-validator"):
    print(name, client.get_prompt_version_by_alias(name, "locked").version)
PY
```
