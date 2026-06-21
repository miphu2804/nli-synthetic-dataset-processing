# Fix 02 — Paraphrase Revalidation Promotion

Proposed branch: `fix/paraphrase-revalidation-promotion`

## Problem

The post-PMI paraphrase stage creates `paraphrase_revalidation_masked.csv`, but
the validation runtime cannot consume that file as the next validation input.
`start_validation_run` currently requires a label-bearing generated dataset and
explicitly says not to pass a pre-masked file.

This means Layer 4 is not actually executable end-to-end: paraphrased rows can
be queued for semantic revalidation, but there is no deterministic path to run
that queue, compare the new verdicts, and promote accepted rewrites into the
publishable dataset.

## Verified Evidence

- `backend/src/cli.py` writes `paraphrased_dataset.csv` and
  `paraphrase_revalidation_masked.csv`.
- `backend/src/providers/validation_provider.py` describes `start_validation_run`
  input as requiring a `label` column and says not to pass a pre-masked file.
- `backend/src/services/validation_run_service.py` rejects datasets missing the
  `label` column.
- `docs/vi/flow/validator.md` says `paraphrase_revalidation_masked.csv` should
  feed into Layer 1 before promotion, but the runtime contract does not yet
  support that handoff.

## Scope

- Add a deterministic revalidation-and-promotion contract for paraphrased rows.
- Keep the trusted expected label source explicit; do not infer labels from row
  order or source UID sequence.
- Promote only rows whose revalidation verdict preserves the intended label.
- Keep rejected revalidation rows in a review artifact with reasons.

## Out Of Scope

- Do not expose this through MCP until the CLI/service contract is proven.
- Do not change PMI scoring or paraphrase generation behavior.
- Do not implement dataset split in this branch.

## Acceptance Criteria

- There is a documented command or service function that accepts:
  `paraphrased_dataset.csv`, `paraphrase_revalidation_masked.csv`, trusted labels,
  and three verdict files for changed rows.
- It emits a final promoted dataset plus a rejected/review artifact.
- It rejects missing, duplicate, or extra UIDs before writing final outputs.
- It has tests for accept, reject, missing UID, duplicate UID, and invalid label.

## Verification

```bash
cd backend
uv run pytest -q
uv run python -m src.cli --help
```
