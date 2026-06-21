# Fix 03 — Persist Consensus PMI Artifacts

Proposed branch: `fix/persist-consensus-pmi-artifacts`

## Problem

The deterministic aggregate and PMI commands work, but the repo does not
currently contain persisted outputs for the real end-to-end corpus state. During
the monitor run no `validation_votes.csv`, `validated_dataset.csv`,
`review_dataset.csv`, `pmi_artifact_tokens.csv`, or `pmi_flagged_rows.csv` was
found in the repo.

Without persisted artifacts or an explicit output convention, the next operator
cannot tell whether the large-scale corpus has reached consensus validation,
PMI review, or is still only at per-model validation.

## Verified Evidence

- `python -m src.cli aggregate` exists and writes `validation_votes.csv`,
  `validated_dataset.csv`, and `review_dataset.csv`.
- `python -m src.cli pmi` exists and writes `pmi_artifact_tokens.csv` and
  `pmi_flagged_rows.csv`.
- A smoke run on round-01 artifacts in a temp directory succeeded:
  `50 rows -> 43 keep, 2 review, 5 discard`; PMI on retained rows flagged `0`
  artifact rows at default threshold.
- Repository search found no persisted consensus or PMI artifacts.

## Scope

- Define the canonical output directory for consensus and PMI artifacts.
- Add a scripted or documented command sequence for the real corpus.
- Ensure generated outputs are either intentionally committed or intentionally
  ignored with a clear handoff path.
- Validate row counts and UID coverage after each stage.

## Out Of Scope

- Do not change consensus rules unless tests prove a bug.
- Do not run outward actions or model calls.
- Do not implement paraphrase promotion or split here.

## Acceptance Criteria

- One documented command sequence produces all consensus and PMI artifacts.
- The output location is consistent with `docs/vi/flow/validator.md` and
  `docs/en/flow/validator.md`.
- The handoff report includes counts for total, keep, review, discard, PMI
  tokens, and PMI flagged rows.
- The repo has tests or a smoke fixture proving the command sequence remains
  runnable.

## Verification

```bash
cd backend
uv run pytest -q
uv run python -m src.cli aggregate --help
uv run python -m src.cli pmi --help
```
