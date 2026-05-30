# NLI Synthetic Data — Generator

Generate 3-class (entailment / neutral / contradiction) hypothesis pairs from premises using 19 rule-based transformations, controlled by adversarial difficulty tier.

## Generation Rules — Entailment (9 rules)

Example premise: *"Người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị áp dụng hình thức khiển trách."* (Juvenile Justice Law)

| Rule | Technique | Example hypothesis |
|------|-----------|--------------------|
| Voice flip | Switch active↔passive, keep semantics | "Hình thức khiển trách có thể được áp dụng đối với người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." |
| Synonym swap | Replace entity with legal equivalent | "Người chưa thành niên từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." |
| Clause restructure | NP ↔ clause conversion | "Việc áp dụng hình thức khiển trách có thể xảy ra nếu người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." |
| Conditional rephrase | Reformat if-then, keep logic | "Trong trường hợp người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý, hình thức khiển trách có thể được áp dụng." |
| Number equivalence | Express numbers differently | "Người từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." (từ đủ 16 = từ 16) |
| Complexity expand | Add subordinate clauses | "Người từ đủ 16 tuổi đến dưới 18 tuổi, theo quy định của Bộ luật Hình sự, nếu phạm tội nghiêm trọng do vô ý thì có thể bị áp dụng hình thức khiển trách." |
| Logical consequence | Derive implicit consequence | "Hành vi phạm tội nghiêm trọng do vô ý của người từ đủ 16 đến dưới 18 tuổi không bị coi là tội phạm đặc biệt nghiêm trọng." |
| General to specific | Apply broad rule to narrow case | "Người 17 tuổi phạm tội trộm cắp nghiêm trọng do vô ý có thể bị khiển trách." |
| Related clause link | Reference genuinely related clauses | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách, đồng thời phải chịu sự giám sát của gia đình theo quy định tại khoản 3 Điều 40." |

## Generation Rules — Contradiction (5 rules)

| Rule | Technique | Example hypothesis | Why contradicted |
|------|-----------|--------------------|------------------|
| Direct negation | Negate core claim | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý không phải chịu bất kỳ hình thức xử lý nào." | "có thể bị khiển trách" → "không phải chịu..." |
| Scope shift | Move subject outside premise range | "Người dưới 16 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "từ đủ 16" → "dưới 16" |
| Modifier flip | Invert a key modifier | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do cố ý có thể bị khiển trách." | "vô ý" → "cố ý" (mens rea flipped) |
| Severity escalation | Escalate condition beyond premise scope | "Người từ đủ 16 đến dưới 18 tuổi phạm tội đặc biệt nghiêm trọng do vô ý có thể bị khiển trách." | "nghiêm trọng" → "đặc biệt nghiêm trọng" |
| Number distortion | Change values to invalidate | "Người từ đủ 14 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "16" → "14" (age threshold lowered) |

## Generation Rules — Neutral (5 rules)

| Rule | Technique | Example hypothesis | Why neutral |
|------|-----------|--------------------|-------------|
| Fallacious reasoning | Plausible-but-wrong logic chain | "Vì người từ đủ 16 đến dưới 18 tuổi có thể bị khiển trách, nên mọi người dưới 18 tuổi phạm tội đều bị khiển trách." | Fallacy of composition: "some → all" |
| Unsupported claim | Inject unstated assertion | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý phải bồi thường thiệt hại và bị khiển trách." | "bồi thường thiệt hại" not in premise |
| Rule misapplication | Apply rule to wrong context | "Người từ đủ 16 đến dưới 18 tuổi phạm tội ít nghiêm trọng do vô ý có thể bị phạt tù." | Wrong penalty for wrong crime class |
| Irrelevant link | Link to unrelated provision | "Người từ đủ 16 đến dưới 18 tuổi...có thể bị khiển trách và bị tịch thu tài sản." | "tịch thu tài sản" from unrelated provision |
| Independent statement | Generate unrelated claim | "Người chưa thành niên phạm tội được hưởng chính sách khoan hồng đặc biệt của Nhà nước." | High-level policy ≠ specific provision |

## Adversarial Difficulty Tiers

Each rule is assigned to exactly one tier. Every tier has at least 1 rule for each label so a single premise can always draw from 3 different tiers.

| Tier | Entailment | Contradiction | Neutral | Target |
|------|-----------|---------------|---------|--------|
| **Surface** | Voice flip, Synonym swap, Number equivalence | Number distortion | Independent statement | Easy — lexical/syntactic transforms, obvious surface changes |
| **Structural** | Clause restructure, Conditional rephrase, Complexity expand | Scope shift, Modifier flip | Irrelevant link | Medium — clause-level changes, scope modifiers, cross-refs |
| **Deep Semantic** | Logical consequence, General to specific, Related clause link | Direct negation, Severity escalation | Fallacious reasoning, Unsupported claim, Rule misapplication | Hard — multi-step inference, implicit consequences, plausible-but-wrong logic, high lexical overlap |

**Deep Semantic hardening (per sample):**
- Maximize lexical overlap premise↔hypothesis (>60% Jaccard) while flipping the label
- Plant high-PMI cue words in WRONG label context (e.g., "Theo quy định" in contradiction/neutral)
- Generate plausible-but-wrong reasoning chains that read like real legal analysis
- Subtle scope/timeframe shifts that change meaning by only 1–2 words

## Anti-Artifact Constraints

Label-leaking cue words to avoid (unless semantically required by the premise):

| Cue word | Biases toward | Replace with |
|----------|---------------|--------------|
| "Dù", "mặc dù", "tuy", "dẫu" | Contradiction / Neutral | Only if semantically justified |
| "không cần", "chẳng cần", "bất kể" | Contradiction / Neutral | Only if semantically justified |
| "tự do" | Contradiction / Neutral | Only if semantically justified |
| "Khi", "một khi", "ngay khi" | Entailment | Only if semantically justified |
| "Theo quy định", "căn cứ", "dựa theo" | Entailment | Only if semantically justified |
| "đồng thời" | Entailment | Only if semantically justified |

## Generation Workflow (Agent-in-the-loop)

This skill runs as a **manual sandbox loop** — you (the AI agent) are the generator. You read premises, assign rules, write hypotheses yourself, then write output via `write_dataset`. There is no separate generator API endpoint.

### Phase 0 — Setup & Confirm

1. Read the input dataset file to verify it exists and is readable
2. Print: total rows, columns, sample first 3 rows
3. Confirm with user:
   - **How many premises** to process? (default: all rows)
   - **Chunk size**: read 5–10 premises at a time (small to avoid safety filter / truncation)
   - **Output filename**: user decides; suggest `{input_name}_nli_adversarials.csv` as default

### Phase 1 — Batch Loop

Process premises in **chunks of 5–10**. For each chunk:

#### 1.1 Read chunk
Read a small batch from the dataset. If `read_dataset` output is truncated, use smaller `batch_size` or read via shell `head`/`tail`.

#### 1.2 Assign rules
For each premise, assign exactly 3 rules — 1 per label, each from a different tier. Rotate tier offset per premise:

```
Premise #1: entailment→Surface,      contradiction→Structural,      neutral→Deep Semantic
Premise #2: entailment→Structural,    contradiction→Deep Semantic,   neutral→Surface
Premise #3: entailment→Deep Semantic, contradiction→Surface,         neutral→Structural
Premise #4: (repeat cycle)
```

Track rule usage count. Prefer least-used rule within each (tier, label) group.

#### 1.3 Generate hypotheses
**You (the AI agent) write each hypothesis directly.** For each premise, apply the 3 assigned rules to produce 3 hypotheses. The hypothesis must be in **Vietnamese**, logically match its label, and follow the rule's technique.

Each output row: `source_uid, premise, hypothesis, label, rule, tier, reason`

#### 1.4 Quick validation (per sample)
Before finalizing, check:

| Gate | Check | Fix if fail |
|------|-------|-------------|
| Label match | Does hypothesis logically entail/contradict/neutral? | Rewrite |
| Rule fit | Does the transformation match the assigned rule? | Rewrite or swap rule |
| Anti-artifact | Any leaking cue word? (see table above) | Remove cue word |
| Vietnamese | Natural grammar, no English words | Fix |

Skip premise entirely if premise text is nonsensical or all 3 retries fail.

#### 1.5 Translate to Vietnamese (if premise is not already Vietnamese)
The agent translates each hypothesis to Vietnamese directly during generation. If the source premise is in another language, translate premise + hypothesis together so meaning stays aligned.

#### 1.6 Write chunk
Use `write_dataset` to write rows. **Important**: `output.path` must be a full file path, not a directory.

- First chunk → creates the file
- Subsequent chunks → **write to separate part files**: `{output_name}_part{N}.csv`

(Note: `write_dataset` does not support append mode, so each chunk goes to its own file.)

#### 1.7 Report progress
After each chunk: `Done chunk N. Rows this chunk: X. Cumulative: Y. Labels: E/C/N = a/b/c.`

### Phase 2 — Continue Until Done

Repeat Phase 1 until target reached or all premises processed.

### Phase 3 — Merge & Final Report

After all chunks are written, optionally merge part files into one:

```bash
head -1 {output_name}_part1.csv > {output_name}.csv
tail -n +2 -q {output_name}_part*.csv >> {output_name}.csv
```

Final report:

| Metric | Value |
|--------|-------|
| Total premises processed | X |
| Total hypotheses generated | X × 3 |
| Entailment / Contradiction / Neutral | E / C / N |
| Surface / Structural / Deep Semantic | Sf / St / Ds |
| Rule distribution | per-rule counts |
| Skipped premises | Z (with reasons) |
| Output file(s) | path(s) |

## Output Schema

`source_uid, premise, hypothesis, label, rule, tier, reason`

- `label`: `entailment` | `neutral` | `contradiction`
- `rule`: one of the 19 rule names above
- `tier`: `surface` | `structural` | `deep_semantic`
- `reason`: short explanation of why this label + rule applies (for QA/debugging)
