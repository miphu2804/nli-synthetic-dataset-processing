# Validator Skill

Validate generated Vietnamese legal NLI rows without seeing the expected_label.

## Input Contract

Each claimed row includes:

```json
{
  "source_uid": "original row id",
  "premise": "Vietnamese legal premise",
  "hypothesis": "Vietnamese legal hypothesis",
  "label": ""
}
```

The empty `label` field means the expected label is intentionally hidden. Do
not infer the hidden label from metadata, row order, batch id, or prior
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

This is a **3-class** task. Return `predicted_label` as exactly one of three
canonical names — `entailment`, `neutral`, or `contradiction`. Do not return
numeric ids; the server maps the canonical name onto the run's numeric label
space (0 = entailment, 1 = neutral, 2 = contradiction).

> Note: this project uses 3 classes, unlike the binary ViLegalNLI paper. The
> paper's single "non-entailment" is split here into `neutral` (insufficient
> support) and `contradiction` (conflict) — keep them distinct.

`reason` MUST be written in **Vietnamese only**. Do not mix English sentences or
phrases. Proper nouns and legal citations (e.g. "Điều 40", names, "compact")
may stay in their original form, but every explanatory clause is Vietnamese.
The reason must be specific enough that a reviewer can see why the label was
chosen from the premise and hypothesis alone.

## Scoring Rubric

Assign the label by judging the logical relation:

| Relation | Use when |
|----------|----------|
| `entailment` | The premise gives enough information to support the hypothesis, or the hypothesis is semantically equivalent within the legal context. |
| `neutral` | The hypothesis is plausible but the premise neither proves nor contradicts it (insufficient support). |
| `contradiction` | The hypothesis conflicts with, negates, or violates the premise. |

Never invent extra labels. The server maps the canonical name onto the run's
numeric ids when needed.

## Checks

- The returned `source_uid` set must match the claimed batch exactly.
- Use only `premise`, `hypothesis`, and the label rubric.
- Do not use metadata, row order, batch id, or prior outputs to infer a label.
- Mention uncertainty, ambiguity, artifact cues, or unnatural wording inside
  `reason` when it affects the label decision.
