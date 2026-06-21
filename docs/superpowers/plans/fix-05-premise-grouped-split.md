# Fix 05 — Premise Grouped Split

Proposed branch: `fix/premise-grouped-split`

Status: implemented on `fix/premise-grouped-split`.

## Problem

The final data split stage is still missing. The CLI has `split` commented as
future work, while the paper-facing docs require all hypotheses derived from the
same premise to remain in the same split.

Without a deterministic premise-grouped split, the pipeline can produce a
validated dataset but cannot safely create train/dev/test artifacts without
risking premise leakage across splits.

## Verified Evidence

- `backend/src/cli.py` has `# "split": _run_split_command` and
  `# _add_split_parser(subparsers)` commented as future work.
- `docs/paper_explanation.md` describes dataset splitting after validation and
  artifact mitigation, with premise grouping as a constraint.
- `docs/PROGRESS.md` lists deterministic premise-grouped `8:1:1` split as a
  remaining issue.

## Scope

- Add deterministic split logic for the final validated/promoted dataset.
- Group by premise or a stable premise key so related hypotheses never cross
  split boundaries.
- Use a fixed seed and clear ratio defaults.
- Emit train/dev/test CSVs plus a manifest with counts and label distribution.

## Out Of Scope

- Do not change validation, PMI, or paraphrase behavior.
- Do not infer that split can run before paraphrase revalidation/promotion is
  complete.

## Acceptance Criteria

- CLI exposes a `split` command with explicit input, output directory, seed, and
  ratio arguments.
- Split output contains no premise overlap across train/dev/test.
- Tests cover grouping, deterministic seed behavior, small datasets, and invalid
  ratios.
- Docs mention split only after the final promoted dataset exists.

## Implemented Fix

- Added deterministic grouped split utility with default `0.8/0.1/0.1` ratios
  and seed `13`.
- Added CLI `split` that writes `train.csv`, `dev.csv`, `test.csv`, and
  `split_manifest.json`.
- Manifest records seed, ratios, row/group counts, and label distribution.
- Added tests for grouping, deterministic seed behavior, small datasets, invalid
  ratios, and CLI output.

## Verification

```bash
cd backend
uv run pytest -q
uv run python -m src.cli split --help
```
