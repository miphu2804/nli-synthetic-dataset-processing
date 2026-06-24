# NLI Synthetic Data - Plain Generator

Read `skill://instructor` first. Use this resource when the source rows already
contain a valid NLI relation, such as ANLI-derived premise/hypothesis pairs.

Translate pre-labeled English NLI pairs to natural Vietnamese while preserving
the original premise-hypothesis relation and expected_label. Do not add a new
adversarial transformation unless the user explicitly asks for it.

## Plain Translation Rules

For each claimed row:

1. Translate `premise` and `hypothesis` to natural Vietnamese.
2. Preserve the original NLI relationship exactly.
3. Preserve the expected_label exactly.
4. Keep named entities, numbers, dates, quantities, and scope constraints faithful
   to the source.
5. Naturalize wording only when it improves Vietnamese readability without
   changing the logical relation.

## Anti-Artifact Constraints

Avoid label-leaking cue words unless required by the source meaning:

| Cue words | Common bias |
|-----------|-------------|
| `Dù`, `mặc dù`, `tuy`, `dẫu` | contradiction / neutral |
| `không cần`, `chẳng cần`, `bất kể` | contradiction / neutral |
| `Khi`, `một khi`, `ngay khi` | entailment |
| `Theo quy định`, `căn cứ`, `dựa theo`, `đồng thời` | entailment |

If a cue word is required by the source meaning, keep it and note that in the
batch stats or skipped-row reason if relevant.

## Self-Checks

Run these checks before returning or submitting each row:

| Gate | Requirement |
|------|-------------|
| Label | Same logical relationship as the original row |
| Language | Premise and hypothesis are natural Vietnamese |
| Fidelity | Entities, numbers, time, negation, and scope match the source |
| Artifact | No unnecessary label-leaking cue words |
| No extra transform | Hypothesis is not made harder or more adversarial than the source |

Retry a failed row up to 3 times. After that, submit it in `skipped_rows` with a
reason and `retries=3`.

## Output Schema

```csv
source_uid,premise,hypothesis,label
```

`label` remains unchanged from the input dataset.
