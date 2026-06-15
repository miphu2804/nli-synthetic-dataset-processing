# Validator Skill

Validate generated Vietnamese legal NLI rows without seeing the original label.

## Input Contract

Each claimed row includes:

```json
{
  "source_uid": "original row id",
  "premise": "Vietnamese legal premise",
  "hypothesis": "Vietnamese legal hypothesis",
  "masked_label": "[MASK]"
}
```

Do not infer the hidden label from metadata, row order, batch id, or prior
outputs. Judge only whether the hypothesis follows from the premise.

## Output Contract

Return one verdict per claimed `source_uid`:

```json
{
  "source_uid": "original row id",
  "predicted_label": "label you assign",
  "reason": "why the premise-hypothesis relation has this label"
}
```

`reason` is the audit explanation. It must be specific enough that a reviewer can
see why the label was chosen from the premise and hypothesis alone.

## Scoring Rubric

Assign the label by judging the logical relation:

| Relation | Use when |
|----------|----------|
| `entailment` | The premise gives enough information to support the hypothesis. |
| `contradiction` | The hypothesis conflicts with, negates, or violates the premise. |
| `neutral` | The hypothesis is plausible but not proven or contradicted by the premise. |

If the run uses numeric label ids, return the exact id required by the run
mapping. Do not invent extra labels. Explain the semantic relation in `reason`
even when `predicted_label` is numeric.

## Checks

- The returned `source_uid` set must match the claimed batch exactly.
- Use only `premise`, `hypothesis`, and the label rubric.
- Do not use metadata, row order, batch id, or prior outputs to infer a label.
- Mention uncertainty, ambiguity, artifact cues, or unnatural wording inside
  `reason` when it affects the label decision.
