# NLI Synthetic Data - Generator

Read `skill://instructor` first. This resource covers only the generation phase.

Translate pre-labeled English NLI pairs to Vietnamese and apply one adversarial
transformation while preserving the expected_label.

## Generation Rules - Entailment

| Rule | Technique |
|------|-----------|
| Voice flip | Switch active/passive voice while keeping semantics |
| Synonym swap | Replace an entity with a valid equivalent |
| Clause restructure | Convert noun phrases and clauses |
| Conditional rephrase | Reformat if-then logic without changing meaning |
| Number equivalence | Express the same numeric condition differently |
| Complexity expand | Add a semantically valid subordinate clause |
| Logical consequence | Derive a supported implicit consequence |
| General to specific | Apply a broad rule to a valid narrow case |
| Related clause link | Add a genuinely supported related clause |

## Generation Rules - Contradiction

| Rule | Technique |
|------|-----------|
| Direct negation | Negate the core claim |
| Scope shift | Move the subject outside the valid range |
| Modifier flip | Invert a key modifier |
| Severity escalation | Change a condition beyond the premise scope |
| Number distortion | Change a numeric value to invalidate the claim |

## Generation Rules - Neutral

| Rule | Technique |
|------|-----------|
| Fallacious reasoning | Add a plausible but unsupported logic chain |
| Unsupported claim | Inject an unstated assertion |
| Rule misapplication | Apply the rule to the wrong context |
| Irrelevant link | Link an unrelated provision |
| Independent statement | Add a related but unsupported statement |

## Anti-Artifact Constraints

Avoid label-leaking cue words unless required by the source meaning:

| Cue words | Common bias |
|-----------|-------------|
| `Dù`, `mặc dù`, `tuy`, `dẫu` | contradiction / neutral |
| `không cần`, `chẳng cần`, `bất kể` | contradiction / neutral |
| `Khi`, `một khi`, `ngay khi` | entailment |
| `Theo quy định`, `căn cứ`, `dựa theo`, `đồng thời` | entailment |

## Generation Phase

For each claimed row:

1. Translate both `premise` and `hypothesis` to natural Vietnamese.
2. Select one rule compatible with the expected_label. Prefer less-used rules.
3. Apply that rule to the hypothesis.
4. Preserve the expected_label.
5. Run these self-checks before returning or submitting the row:

| Gate | Requirement |
|------|-------------|
| Label | Same logical relationship as the original row |
| Rule | Assigned transformation is visible |
| Language | Premise and hypothesis are natural Vietnamese |
| Artifact | No unnecessary label-leaking cue words |
| Change | Transformed hypothesis differs from the original |

Retry a failed row up to 3 times. After that, submit it in `skipped_rows` with a
reason and `retries=3`.

## Output Schema

```csv
source_uid,premise,hypothesis,label
```

`label` remains unchanged from the input dataset.
