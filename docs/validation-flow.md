# Offline Validation Flow

This flow keeps validation blind: model validators read only a dataset with the
label values removed, then a trusted aggregator compares model labels and runs
artifact checks.

## 1. Create the Masked Dataset

Run this step only in the trusted runtime that can read the original labels.

Interactive CLI:

```bash
uv run python -m src.utils.validation_masking_cli
```

Scripted CLI:

```bash
uv run python -m src.utils.validation_masking_cli \
  --input data/generated/generated.csv \
  --output data/validation/validation_masked.csv \
  --uid-column source_uid \
  --yes
```

```python
import pandas as pd

from src.utils.validation_masking import write_masked_validation_dataset

source = pd.read_csv("data/generated/generated.csv")
write_masked_validation_dataset(
    source,
    output_path="data/validation/validation_masked.csv",
    uid_column="source_uid",
)
```

The masked dataset contains only:

```text
source_uid,premise,hypothesis,masked_label
```

Do not give validators the original generated file.

## 2. Run Independent Validators

Each model receives `validation_masked.csv` and writes one verdict file named
after the model.

```text
data/validation/gpt4o.csv
data/validation/deepseek.csv
data/validation/llama.csv
```

Each model file must contain:

```text
source_uid,predicted_label,reason
```

The minimum required columns for aggregation are:

```text
source_uid,predicted_label,reason
```

Validators must not receive filesystem access to the original labeled dataset.
Each validator must read `skill://validator` before labeling so it uses the same
NLI label rubric and writes `reason` as the complete explanation for the chosen
label.

## 3. Build Vote Consensus and PMI

Run the aggregation CLI (interactive or scripted):

```bash
uv run python -m src.utils.validation_aggregation_cli
```

```bash
uv run python -m src.utils.validation_aggregation_cli \
  --verdicts-dir data/validation \
  --masked-input data/validation/validation_masked.csv \
  --output-dir data/validation \
  --min-joint-count 3 \
  --yes
```

The CLI writes two files:

- `validation_votes.csv` — one row per sample with per-model label columns, vote counts,
  `consensus_label`, `consensus_size`, and `agreement_status`.
- `pmi_consensus.csv` — PMI scores for token-label pairs from the `hypothesis` column,
  filtered to tokens with joint count ≥ `--min-joint-count`.

Or use the Python API directly:

```python
from src.utils.validation_aggregation import build_validation_vote_table

votes = build_validation_vote_table(
    {
        "gpt4o": "data/validation/gpt4o.csv",
        "deepseek": "data/validation/deepseek.csv",
        "llama": "data/validation/llama.csv",
    }
)
votes.to_csv("data/validation/validation_votes.csv", index=False)
```

The vote table contains one label column per model, vote counts, and:

```text
consensus_label,consensus_size,agreement_status
```

Agreement status:

```text
unanimous  all models agree
majority   at least two models agree
review     no reliable majority
```

## 4. Trusted Final Decision

The trusted runtime can compare `consensus_label` to the hidden original label:

```text
accepted=true   consensus matches original label
accepted=false  consensus contradicts original label
manual review   no majority or ambiguous semantic/legal case
```

This mirrors the paper-style validation idea: independent re-annotation without
original labels, consensus filtering, and manual review for weak agreement.

For MCP runtime validation, finalization writes one CSV rather than splitting the
outputs:

```text
validation_results.csv
```

Schema:

```text
source_uid,premise,hypothesis,expected_label,predicted_label,accepted,reason
```

`accepted` is computed by the trusted runtime as
`predicted_label == expected_label`. PMI remains a separate CLI analysis step.
