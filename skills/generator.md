# NLI Synthetic Data — Generator

Generate entailment/non-entailment hypothesis pairs from premises using 19 rule-based transformations, controlled by adversarial difficulty tier. Adapted from ViLegalNLI (arXiv:2605.00116).

## Generation Rules — Entailment (9 rules)

Example premise: *"Người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị áp dụng hình thức khiển trách."* (Juvenile Justice Law)

| ID | Rule | Technique | Example hypothesis |
|----|------|-----------|--------------------|
| E1 | Active–passive | Switch voice, keep semantics | "Hình thức khiển trách có thể được áp dụng đối với người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." |
| E2 | Entity synonym | Swap with legal equivalent | "Người chưa thành niên từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." |
| E3 | Nominal–clausal | NP ↔ clause | "Việc áp dụng hình thức khiển trách có thể xảy ra nếu người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." |
| E4 | Conditional reform | Reformat if-then, keep logic | "Trong trường hợp người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý, hình thức khiển trách có thể được áp dụng." |
| E5 | Equivalent number | Express numbers differently | "Người từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." (từ đủ 16 = từ 16) |
| E6 | Complexity expand | Add subordinate clauses | "Người từ đủ 16 tuổi đến dưới 18 tuổi, theo quy định của Bộ luật Hình sự, nếu phạm tội nghiêm trọng do vô ý thì có thể bị áp dụng hình thức khiển trách." |
| E7 | Logical consequence | Derive implicit consequence | "Hành vi phạm tội nghiêm trọng do vô ý của người từ đủ 16 đến dưới 18 tuổi không bị coi là tội phạm đặc biệt nghiêm trọng." |
| E8 | General→specific | Apply broad rule to narrow case | "Người 17 tuổi phạm tội trộm cắp nghiêm trọng do vô ý có thể bị khiển trách." |
| E9 | Related clause link | Reference genuinely related clauses | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách, đồng thời phải chịu sự giám sát của gia đình theo quy định tại khoản 3 Điều 40." |

## Generation Rules — Non-entailment (10 rules)

| ID | Rule | Technique | Example hypothesis | Why non-entailed |
|----|------|-----------|--------------------|------------------|
| NE1 | Structural contradiction | Negate core claim | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý không phải chịu bất kỳ hình thức xử lý nào." | "có thể bị khiển trách" → "không phải chịu..." |
| NE2 | Entity/scope alter | Shift subject outside premise range | "Người dưới 16 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "từ đủ 16" → "dưới 16" |
| NE3 | Semantic inconsistency | Flip a key modifier | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do cố ý có thể bị khiển trách." | "vô ý" → "cố ý" (mens rea flipped) |
| NE4 | Contradictory condition | Escalate condition severity | "Người từ đủ 16 đến dưới 18 tuổi phạm tội đặc biệt nghiêm trọng do vô ý có thể bị khiển trách." | "nghiêm trọng" → "đặc biệt nghiêm trọng" |
| NE5 | Number modification | Change values to invalidate | "Người từ đủ 14 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "16" → "14" (age threshold lowered) |
| NE6 | Invalid reasoning | Plausible-but-wrong logic chain | "Vì người từ đủ 16 đến dưới 18 tuổi có thể bị khiển trách, nên mọi người dưới 18 tuổi phạm tội đều bị khiển trách." | Fallacy of composition: "some → all" |
| NE7 | Unsupported assumption | Inject unstated claim | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý phải bồi thường thiệt hại và bị khiển trách." | "bồi thường thiệt hại" not in premise |
| NE8 | Rule misapplication | Apply rule to wrong context | "Người từ đủ 16 đến dưới 18 tuổi phạm tội ít nghiêm trọng do vô ý có thể bị phạt tù." | Wrong penalty for wrong crime class |
| NE9 | Unrelated clause link | Link to irrelevant provision | "Người từ đủ 16 đến dưới 18 tuổi...có thể bị khiển trách và bị tịch thu tài sản." | "tịch thu tài sản" from unrelated provision |
| NE10 | Independent statement | Generate unrelated claim | "Người chưa thành niên phạm tội được hưởng chính sách khoan hồng đặc biệt của Nhà nước." | High-level policy ≠ specific provision |

## Adversarial Difficulty Tiers

| Tier | Rules to use | Model Acc | Technique |
|------|-------------|-----------|-----------|
| **Surface** | E1, E2, E3, E5, NE4, NE5, NE9, NE10 | ≥90% | Lexical/syntactic transforms only: voice flip, synonym swap, number change, direct negation |
| **Structural** | E4, E6, E7, NE1, NE2, NE3, NE8 | 80–90% | Add subordinate clauses, cross-refs, scope modifiers. Maintain grammar, increase complexity |
| **Deep Semantic** | E8, E9, NE6, NE7 | <80% | Multi-step inference. Implicit legal consequences. Plausible-but-wrong logic chains. High lexical overlap with flipped label |

**Level 4 (hardest adversarial):**
- Maximize lexical overlap premise↔hypothesis (>60% Jaccard) while flipping the label
- Plant high-PMI cue words in WRONG label context (e.g., "Theo quy định" in non-entailment)
- Generate plausible-but-wrong reasoning chains that read like real legal analysis
- Subtle scope/timeframe shifts that change meaning by only 1–2 words

## Anti-Artifact Constraints

Label-leaking cue words to avoid (unless semantically required by the premise):

| Cue word | Biases toward | Replace with |
|----------|---------------|--------------|
| "Dù", "mặc dù", "tuy", "dẫu" | Non-entailment | Only if semantically justified |
| "không cần", "chẳng cần", "bất kể" | Non-entailment | Only if semantically justified |
| "tự do" | Non-entailment | Only if semantically justified |
| "Khi", "một khi", "ngay khi" | Entailment | Only if semantically justified |
| "Theo quy định", "căn cứ", "dựa theo" | Entailment | Only if semantically justified |
| "đồng thời" | Entailment | Only if semantically justified |

## How to Use This Skill

### Step 1: Read premises
Use `read_dataset_with_pandas` to load premises from CSV/parquet. The dataset must have a text column containing premises (e.g., `premise`).

### Step 2: Generate hypotheses
For each premise, generate an entailment hypothesis and a non-entailment hypothesis. Pick rules from the adversarial tier matching your target difficulty:

- **Quick dataset (Surface tier):** E1,E2 + NE1,NE10 — fast to generate, models score ≥90%
- **Balanced dataset (Structural tier):** E4,E7 + NE2,NE3 — requires clause-level reasoning
- **Hard benchmark (Deep Semantic tier):** E8,NE6,NE7 — multi-step inference, 22% model error rate

### Step 3: Translate to Vietnamese (if source is other language)
Use `translate_dataset_with_chatgpt` with `text_columns=["premise", "hypothesis"]` and `target_language="Vietnamese"`. Set `pass_through=true` if no API key — rows return untranslated for manual MCP/Web translation.

### Step 4: Write output
Use `write_dataset_output` to save generated pairs as CSV.

### Step 5: Validate quality (see `skill://validator`)
Cross-model consensus filtering, PMI artifact detection, hypothesis-only baseline.

## Reference

ViLegalNLI: Natural Language Inference for Vietnamese Legal Texts, arXiv:2605.00116 (Apr 2026).
