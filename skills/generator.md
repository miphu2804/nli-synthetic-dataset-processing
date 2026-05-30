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

**IMPORTANT**: The input dataset already has `premise`, `hypothesis`, and `label` columns — these are pre-labeled NLI pairs (usually in English). The task is to **translate both to Vietnamese** then **adversarially transform** the hypothesis (or premise) to increase difficulty, while **keeping the original label unchanged**.

This skill runs as a **manual sandbox loop** — you (the AI agent) do the translation and transformation. There is no separate generator API endpoint.

**Before starting**: Load companion skills:
- `get_skill("progress_tracking")` — JSONL event log format, hash chain, event types, bash queries
- `get_skill("delegation")` — subagent prompt template, responsibility split, parallel execution
- `get_skill("execution")` — what runs where: LLM for text, bash for queries, Monty for untrusted or Python code

### Phase 0 — Setup & Confirm

1. **Load progress_tracking skill**: `get_skill("progress_tracking")` — memorize the event schema
2. Read the input dataset to verify columns: must have `premise`, `hypothesis`, `label`
3. Print: total rows, columns, 3 sample rows
4. Initialize `progress.jsonl` with a `run.start` event (see progress_tracking for format: `prev_hash:"0"`)
5. Confirm with user:
   - **How many rows** to process? (default: all)
   - **Chunk size**: 5–10 rows at a time (small to avoid truncation)
   - **Output filename**: user decides; suggest `{input_name}_nli_adversarials.csv`

### Phase 1 — Batch Loop

Process rows in **chunks of 5–10**. For each chunk:

#### 1.1 Read chunk + check progress
- If `progress.jsonl` exists, `tail -1` to find last completed batch → resume from next batch
- If no progress log exists, start fresh from batch 1, row 1
- Read a small batch via `read_dataset`. If truncated, use smaller `batch_size`.

#### 1.2 Translate BOTH premise and hypothesis to Vietnamese
**Do NOT keep either in English.** Translate the full pair together so meaning stays aligned:
- `premise` → Vietnamese
- `hypothesis` → Vietnamese
- The logical relationship (entailment/contradiction/neutral) must survive translation

#### 1.3 Assign adversarial rule
For each translated pair, pick 1 adversarial rule based on the **original label**:

| Original label | Available rules |
|---------------|-----------------|
| entailment (0) | Voice flip, Synonym swap, Clause restructure, Conditional rephrase, Number equivalence, Complexity expand, Logical consequence, General to specific, Related clause link |
| contradiction (2) | Direct negation, Scope shift, Modifier flip, Severity escalation, Number distortion |
| neutral (1) | Fallacious reasoning, Unsupported claim, Rule misapplication, Irrelevant link, Independent statement |

Pick the rule's tier following the rotation: Surface → Structural → Deep Semantic → (repeat). Track rule usage, prefer least-used.

#### 1.4 Apply adversarial transformation
Transform the **hypothesis** (and/or premise if needed) according to the assigned rule:
- **Surface tier**: light lexical/syntactic changes — easy to detect
- **Structural tier**: clause-level changes, scope shifts — medium difficulty
- **Deep Semantic tier**: multi-step inference, subtle changes, high word overlap — hard

**The original label MUST be preserved.** After transformation, the pair must still have the same entailment/contradiction/neutral relationship.

#### 1.5 Validate (per row)
Check each transformed pair:

| Gate | Check | Fix if fail |
|------|-------|-------------|
| Label preserved | Does the transformed pair still match the original label? | Adjust or redo transformation |
| Rule applied | Is the rule transformation clearly visible? | Strengthen the transformation |
| Anti-artifact | Any leaking cue word? | Remove cue word |
| Both Vietnamese | Are premise AND hypothesis both in Vietnamese? | Translate the one that isn't |
| Natural | Grammar and fluency | Fix wording |

Fail 3 times → skip row, log reason.

#### 1.6 Log events to progress.jsonl
After each row: append a `row.done` event. After each batch: append `batch.done`. If a row fails: `row.skip`. See `progress_tracking` for exact field schema (`id`, `prev_hash`, `ts`).

#### 1.7 Write chunk
Use `write_dataset` with full file path. Each chunk → separate file: `{output_name}_part{N}.csv`

Output columns: `source_uid, premise, hypothesis, label, rule, tier, reason`

- `premise`: translated + possibly transformed (Vietnamese)
- `hypothesis`: translated + adversarially transformed (Vietnamese)
- `label`: **same as original** (entailment / neutral / contradiction)
- `rule`: which adversarial rule was applied
- `tier`: surface / structural / deep_semantic

#### 1.8 Report progress
`Done batch N. Rows: X. Cumulative: Y. Labels: E/C/N = a/b/c. Tiers: Sf/St/Ds = d/e/f.`

Also snapshot distribution from CSV: `cut -d',' -f5 output.csv | sort | uniq -c | sort -rn`

### Phase 2 — Continue Until Done

Repeat Phase 1 until target reached. On each resume, check `progress.jsonl` to know where to continue.

### Phase 3 — Merge & Final Report

```bash
head -1 {output_name}_part1.csv > {output_name}.csv
tail -n +2 -q {output_name}_part*.csv >> {output_name}.csv
```

| Metric | Value |
|--------|-------|
| Total rows processed | X |
| Entailment / Neutral / Contradiction | E / N / C |
| Surface / Structural / Deep Semantic | Sf / St / Ds |
| Rule distribution | per-rule counts |
| Skipped | Z (with reasons) |
| Output | path |

## Output Schema

`source_uid, premise, hypothesis, label, rule, tier, reason`

- `label`: `entailment` | `neutral` | `contradiction`
- `rule`: one of the 19 rule names above
- `tier`: `surface` | `structural` | `deep_semantic`
- `reason`: short explanation of why this label + rule applies (for QA/debugging)
