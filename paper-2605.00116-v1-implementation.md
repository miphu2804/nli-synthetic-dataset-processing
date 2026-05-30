x# ViLegalNLI — Synthetic Data Generation Framework

**Paper:** ViLegalNLI: Natural Language Inference for Vietnamese Legal Texts  
**arXiv:** 2605.00116v1 [cs.CL] (30 Apr 2026)  
**Authors:** Nhung Thi-Hong Duong, Mai Ngoc Ho, Tin Van Huynh, Kiet Van Nguyen  
**Venue:** University of Information Technology, VNU-HCMC

---

## Overview Pipeline (7 Steps)

```
[1] Data Collection ──► [2] Preprocessing ──► [3] Premise Extraction
                                                    │
                                                    ▼
[7] Difficulty Eval ◄── [6] Data Validation ◄── [5] Hypothesis Generation
                                                    ▲
                                                    │
                                           [4] Prompt Optimization
```

Two core phases:
- **GENERATOR:** Steps 4-5 (Prompt Optimization → Hypothesis Generation)
- **VALIDATOR:** Steps 6-7 (Data Validation → Difficulty Evaluation)

Result: **42,012 premise–hypothesis pairs** from 168 statutory documents across 27 legal domains.

---

## Phase 1: GENERATOR (Hypothesis Generation)

### Step 4: Prompt Optimization

**Model used for generation:** Gemini-2.5 Flash (primary hypothesis generator)

**Approach:** Iterative prompt refinement through 6 rounds, measured by inter-model agreement (Fleiss' Kappa κ).

**Cross-labeling models (independent verifiers):**
- GPT-4o
- DeepSeek-R1
- LLaMA-4 Scout

**Process:**
1. Write initial instruction-based prompt guiding the model to generate hypotheses under 2 labels: Entailment / Non-entailment
2. Generate hypotheses for 50 sample premises
3. 3 independent models label the generated pairs
4. Compute Fleiss' Kappa to measure inter-model agreement
5. Refine prompt based on linguistic clarity and agreement analysis
6. Repeat until κ ≥ 0.85

**Prompt Refinement History (Table 5):**

| Round | κ    | Main Improvement                           |
|-------|------|--------------------------------------------|
| 1     | 0.67 | Basic prompt, ambiguous hypotheses         |
| 2     | 0.80 | Added clearer inference constraints        |
| 3     | 0.83 | Reduced linguistic ambiguity               |
| 4     | 0.85 | Introduced causal and purposive reasoning  |
| 5     | 0.85 | Increased diversity of legal scenarios     |
| 6     | 0.87 | Multi-clause legal reasoning               |

**Selection criterion:** Prompt achieving κ ≥ 0.85 (near-perfect agreement per Landis & Koch interpretation).

**Key design:** The prompting strategy follows a **structured reasoning paradigm** — the prompt instructs the model to reason step-by-step before generating the hypothesis, ensuring inferential consistency.

**Prompt design principle:** Independent prompts for generator vs. labeling models to maintain evaluation objectivity.

### Step 5: Hypothesis Generation

**Model:** Gemini-2.5 Flash  
**Input:** Premise (from Step 3) + finalized prompt (from Step 4)  
**Output:** Hypothesis with label (Entailment / Non-entailment)

#### Generation Rules (Table 6) — with Concrete Vietnamese Examples

Example premise used throughout (from Law on Juvenile Justice):
> **P:** *"Người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị áp dụng hình thức khiển trách."*
> (A person aged 16 to under 18 who involuntarily commits a serious crime may be subject to a reprimand.)

---

**Entailment Rules (9 rules):**

| ID | Rule | Description | Example Hypothesis (VI) | Key Signal |
|----|------|-------------|--------------------------|------------|
| 1 | Active–passive transformation | Transform voice while preserving semantics | "Hình thức khiển trách có thể được áp dụng đối với người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." | Passive → Active or vice versa; core meaning identical |
| 2 | Entity synonym substitution | Replace entities with synonymous legal references | "Người chưa thành niên từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "Người từ đủ 16 tuổi..." → "Người chưa thành niên..." |
| 3 | Nominal–clausal reformulation | Reformulate noun phrase as clause or vice versa | "Việc áp dụng hình thức khiển trách có thể xảy ra nếu người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý." | "có thể bị áp dụng" (VP) → "Việc áp dụng...có thể xảy ra" (NP) |
| 4 | Conditional reformulation | Reformat conditional structure preserving logic | "Trong trường hợp người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý, hình thức khiển trách có thể được áp dụng." | "Nếu/Trong trường hợp..." fronting; logic chain unchanged |
| 5 | Equivalent numerical modification | Modify numerical expressions equivalently | "Người từ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "từ đủ 16 tuổi" = "từ 16" in legal shorthand |
| 6 | Sentence complexity expansion | Expand sentence without changing meaning | "Người từ đủ 16 tuổi đến dưới 18 tuổi, theo quy định của Bộ luật Hình sự, nếu phạm tội nghiêm trọng do vô ý thì có thể bị áp dụng hình thức khiển trách." | Added "theo quy định của..." parenthetical; core semantics intact |
| 7 | Logical consequence inference | Derive logical consequence from premise | "Hành vi phạm tội nghiêm trọng do vô ý của người từ đủ 16 đến dưới 18 tuổi không bị coi là tội phạm đặc biệt nghiêm trọng." | Implicit consequence: if reprimand applies → crime is not "đặc biệt nghiêm trọng" |
| 8 | General-to-specific rule application | Apply general rule to a specific case | "Người 17 tuổi phạm tội trộm cắp nghiêm trọng do vô ý có thể bị khiển trách." | "Người từ đủ 16 đến dưới 18" → "Người 17 tuổi"; general crime → "tội trộm cắp" |
| 9 | Related clause linking | Link to related clauses without altering meaning | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách, đồng thời phải chịu sự giám sát của gia đình theo quy định tại khoản 3 Điều 40." | Added "đồng thời..." from a genuinely related clause; both statements entailed |

**Non-entailment Rules (10 rules):**

| ID | Rule | Description | Example Hypothesis (VI) | Why Non-entailed |
|----|------|-------------|--------------------------|-------------------|
| 1 | Structural contradiction | Transform structure to introduce contradiction | "Người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý không phải chịu bất kỳ hình thức xử lý nào." | "có thể bị khiển trách" → "không phải chịu bất kỳ..." = direct negation |
| 2 | Entity/time/action alteration | Alter entities, time, or actions | "Người dưới 16 tuổi phạm tội nghiêm trọng do vô ý có thể bị áp dụng hình thức khiển trách." | "từ đủ 16" → "dưới 16" = entity scope shifted outside premise range |
| 3 | Semantic inconsistency | Create semantic inconsistency | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do cố ý có thể bị khiển trách." | "vô ý" → "cố ý" = mens rea flipped; premise only covers involuntary |
| 4 | Contradictory condition insertion | Add conditions that contradict premise | "Người từ đủ 16 đến dưới 18 tuổi phạm tội đặc biệt nghiêm trọng do vô ý có thể bị khiển trách." | Premise says "tội nghiêm trọng" → hypothesis says "tội đặc biệt nghiêm trọng" = contradictory severity |
| 5 | Numerical value modification | Modify numerical values to change meaning | "Người từ đủ 14 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách." | "16" → "14" = age threshold lowered beyond what premise allows |
| 6 | Invalid reasoning statement | Generate logically invalid reasoning | "Vì người từ đủ 16 đến dưới 18 tuổi có thể bị khiển trách, nên mọi người dưới 18 tuổi phạm tội đều bị khiển trách." | Invalid generalization: "some cases → all cases" (fallacy of composition) |
| 7 | Unsupported assumption | Introduce assumption not supported by premise | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý phải bồi thường thiệt hại và bị khiển trách." | "phải bồi thường thiệt hại" = not stated in premise, not logically derivable |
| 8 | Rule misapplication | Misapply general legal rules | "Người từ đủ 16 đến dưới 18 tuổi phạm tội ít nghiêm trọng do vô ý có thể bị phạt tù." | Premise talks about "khiển trách" for "tội nghiêm trọng" → hypothesis applies "phạt tù" to different crime class |
| 9 | Unrelated clause linking | Link to clauses irrelevant to the premise | "Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách và bị tịch thu tài sản." | "tịch thu tài sản" linked from an unrelated legal provision; no connection to reprimand |
| 10 | Independent non-inferable statement | Create statement that cannot be inferred | "Người chưa thành niên phạm tội được hưởng chính sách khoan hồng đặc biệt của Nhà nước." | High-level policy statement; premise is a specific provision, not a general amnesty |

**Key design properties:**
- Each rule targets a specific reasoning type (paraphrasing, logical implication, legally invalid inference)
- No rule is exclusively associated with a single label → reduces rule-based annotation artifacts
- Rules E1, E7 tend to yield more entailment; Rules NE6, NE10 tend to yield more non-entailment (Figure 6)
- Rules NE6, NE7 are the hardest — causing 22% false negatives (Table 16)
- Rules NE1 causes 15% false positives due to high lexical overlap with premise

---

## Phase 2: VALIDATOR (Quality Control)

### Step 6: Data Validation — Cross-Model Consensus Filtering

**Goal:** Reduce single-model bias and ensure label reliability.

**Approach:** Multi-layer evaluation = automatic cross-labeling + manual verification.

**Process:**
1. **3 independent models** re-annotate the entire dataset:
   - GPT-4o
   - DeepSeek-R1
   - LLaMA-4 Scout
2. Models do NOT have access to original Gemini-2.5 Flash labels
3. Decision rule:
   - **≥2 models agree with original label** → retain
   - **0 models agree** → discard
   - **Only 1 model agrees** → manual review (detailed semantic + legal analysis)

**Results (Table 7):**

| Label              | 3-Model Agreement | ≥2-Model Agreement | Only 1 Agrees |
|--------------------|-------------------|---------------------|---------------|
| Non-entailment (0) | 93.28%            | 98.81%              | 1.19%         |
| Entailment (1)     | 62.44%            | 84.75%              | 15.25%        |
| **Total**          | **79.34%**        | **92.45%**          | **7.55%**     |

**Key observation:** Entailment is harder to agree on (62% full agree) vs. Non-entailment (93% full agree). Most disagreements are labeling variation, not true inconsistency. ~1.2% genuinely problematic.

### Step 7: Data Difficulty Evaluation & Artifact Mitigation

**Goal:** Control dataset difficulty and remove annotation artifacts (where models exploit superficial lexical cues instead of semantic reasoning).

#### 7a. Hypothesis-Only Baseline Detection

- Train CafeBERT NLI model on ViLegalNLI → achieves ~90% accuracy (Table 8)
- **Hypothesis-only test:** feed only hypothesis (no premise) → competitive performance
- This indicates **label-correlated lexical patterns** exist → models partially rely on surface signals

#### 7b. PMI-Based Artifact Detection

Compute **Pointwise Mutual Information (PMI)** between hypothesis tokens and labels:

```
PMI(w, y) = log( P(w, y) / (P(w) * P(y)) )
```

- Higher PMI = stronger token-to-label association = potential artifact
- Top artifact tokens identified (Table 13):

| Token (VI)               | Label           | PMI   | Frequency |
|--------------------------|-----------------|-------|-----------|
| "không cần" (not req.)   | Non-entailment  | 0.95  | 13.02%    |
| "Dù" (although)          | Non-entailment  | 0.97  | 8.15%     |
| "bất kể" (regardless)   | Non-entailment  | 0.89  | 4.26%     |
| "Khi" (when)             | Entailment      | 0.99  | 5.52%     |
| "Theo quy định" (acc. to)| Entailment      | 0.98  | 5.44%     |

#### 7c. Controlled Paraphrasing for Artifact Removal

For instances containing high-PMI artifact tokens:
1. **Rewrite hypothesis** via generative model while:
   - Preserving semantic meaning
   - Preserving inference label
   - Removing artifact-related lexical cues
2. **Verify semantic preservation:** cosine similarity between original & revised embeddings
   - Average cosine similarity: **0.883**
   - 55.5% of instances > 0.9 similarity
   - Lower similarity = controlled logical transformations (negation, scope modification), not distortion
3. Substitute with representative variants (Table 9):

| Trigger word     | Label           | Replacement variants                                              |
|------------------|-----------------|-------------------------------------------------------------------|
| "Dù" (although)  | Non-entailment  | Mặc dù, Tuy, Dẫu, Mặc cho, Tuy rằng...                           |
| "Khi" (when)     | Entailment      | Một khi, Ngay khi, Trong khi, Giả sử...                            |
| "Căn cứ" (based) | Entailment      | Dựa theo, Dựa vào, Dựa trên cơ sở...                               |
| "không cần"      | Non-entailment  | Chẳng cần, Không yêu cầu, Không nhất thiết...                      |

---

## Step 3 (Prerequisite): Premise Extraction

Implemented as **rule-based structural extraction** (not LLM). Key design decisions:

- **Unit:** Sentence-level premises from articles, clauses, sub-clauses, and points
- **Context preservation:** Article-level info added when needed (prohibited acts, sanctions, interdependent enumerations)
- **Point handling:** Clause-level context added to ensure semantic completeness

**Rule-based keyword indicators (Table 3):**

| # | Keywords (VI)                                | Position          |
|---|----------------------------------------------|-------------------|
| 1 | "sau đây" (as follows)                       | End of article    |
| 2 | "như sau" (as follows)                       | End of article    |
| 3 | "bao gồm" (including)                        | End of article    |
| 4 | "nghiêm cấm"/"cấm"/"vi phạm"/"bị xử phạt"   | Within article    |
| 5 | "Thứ tự"/"Trình tự" (order/procedure)        | Within article    |

**Metadata recorded per premise (Table 4):**
Law ID, Law Name, Law Date, Field of Law, Chapter, Section, Article, Clause, Point, Premise text, Hypothesis text, Label

**Result:** 20,860 premises extracted from 168 active statutory documents.

---

## Step 4.5 (Important Detail): Dataset Splitting Strategy

**Ratio:** 8:1:1 (Train:Dev:Test)
- 34,121 train / 4,160 dev / 3,731 test

**Anti-leakage rules:**
- All hypotheses from the SAME premise go to the SAME split
- No premise appears in multiple splits
- Label distribution balanced across splits
- Legal sub-domain proportions preserved across splits

---

## Models & Config Summary

| Role                           | Model(s)                                      |
|--------------------------------|-----------------------------------------------|
| Hypothesis Generator           | Gemini-2.5 Flash                              |
| Cross-Model Validators         | GPT-4o, DeepSeek-R1, LLaMA-4 Scout            |
| Artifact Detection (diagnostic)| CafeBERT                                      |
| Baseline NLI (fine-tuned)      | XLM-R, InfoXLM, mBERT, PhoBERT, viBERT, etc. |
| LLM Evaluation (few-shot)      | Qwen2.5-7B-Instruct, Gemma-3-4B-it            |
| LLM Evaluation (zero-shot)     | Gemma-3, Qwen2.5                              |
| LLM Evaluation (fine-tuned)    | Gemma-2                                       |

---

## Key Design Decisions & Rationale

1. **Semi-automatic (not fully manual):** LLM generation + cross-model validation hits the sweet spot between scale and quality. Full manual annotation of 42K pairs would be prohibitively expensive.

2. **Iterative prompt over one-shot:** 6 rounds of prompt refinement with quantitative κ measurement is cheaper than collecting human annotations, yet reaches near-perfect agreement.

3. **Consensus over single-model:** Using 3 diverse models (GPT-4o, DeepSeek-R1, LLaMA-4) for validation reduces single-model bias. Gemini generates, others verify → separation of concerns.

4. **PMI over manual artifact detection:** Statistical detection scales better than manual inspection. Controlled paraphrasing preserves semantics while removing artifacts.

5. **Rule-based premise extraction over LLM:** Structural patterns in legal text are predictable enough for regex/rules — no need for LLM at this stage, saving cost and avoiding hallucination.

6. **Hypothesis-only baseline as quality signal:** If a model can predict the label from hypothesis alone, the dataset has lexical artifacts. This is a cheap, effective diagnostic.

7. **Premise-based split (not random):** Ensures models learn to reason, not to memorize which premise maps to which label.

---

## What This Means for Your Project

Your project (`nli-synthetic-data-processing`) can adopt this framework for Vietnamese NLI data:

1. **Generator Service:** LLM-powered hypothesis generation with rule-based templates. Your existing `TranslationService` pattern (async OpenAI calls + batch processing) maps directly to a `GeneratorService`.

2. **Validator Service:** Cross-model consensus filtering + PMI artifact detection. This is net-new. Needs:
   - Multi-model labeling (could use OpenAI + other providers)
   - PMI computation on hypothesis tokens
   - Controlled paraphrasing for artifact removal

3. **Premise Extractor:** Rule-based regex extraction from structured text. Much simpler than the generator — your `DatasetReaderService` already handles the IO layer.

4. **MCP Tools Design:** The individual-tool approach from our earlier discussion fits here:
   - `generate_hypotheses(premise_path, rules, model, ...)` 
   - `validate_labels(dataset_path, validator_models, ...)`
   - `detect_artifacts(dataset_path, pmi_threshold, ...)`
   - `mitigate_artifacts(dataset_path, artifact_tokens, ...)`

---

## Generator Prompt Template

Based on the paper's 6-round prompt refinement, the final prompt (κ = 0.87) follows a **structured reasoning paradigm** (step-by-step reasoning before generation). Below is the reconstructed prompt template.

### System Prompt

```text
You are a legal reasoning expert for Vietnamese statutory texts. Your task is
to generate hypotheses from a given legal premise. You must follow a structured
chain-of-thought process: first analyze the premise structure, then apply the
specified generation rule, and finally produce the hypothesis.

## Reasoning Process
Before writing the hypothesis, think through these steps:
1. PREMISE PARSING: Identify the legal subject, normative action, conditions,
   and scope of the premise.
2. RULE SELECTION: Confirm which generation rule is being applied.
3. INFERENCE CHECK: Verify that the label (Entailment/Non-entailment) is
   logically justified given the premise.
4. ARTIFACT CHECK: Ensure the hypothesis does NOT contain label-leaking
   trigger words unless they naturally fit the legal context.
5. GENERATION: Write the hypothesis in formal Vietnamese legal language.

## Label Definitions
- ENTAILMENT (1): The hypothesis MUST be logically inferred from the premise
  or be semantically equivalent in the legal context. Use paraphrasing, logical
  consequence derivation, general-to-specific application, etc.
- NON-ENTAILMENT (0): The hypothesis CANNOT be inferred from the premise.
  Includes contradiction, semantic inconsistency, unsupported assumptions,
  misapplication of rules, or independent non-inferable statements.

## Quality Requirements
- Hypothesis must be 25-60 tokens (concise but complete)
- Use formal Vietnamese legal register matching the premise style
- Preserve legal terminology precision
- Avoid label-specific cue words that reveal the answer without reasoning
- Multi-clause reasoning is acceptable and encouraged for complex premises
- Each hypothesis must be independently verifiable against the premise
```

### User Prompt Template

```text
## Premise
{premise}

## Generation Rule
Rule ID: {rule_id}
Rule Name: {rule_name}
Rule Description: {rule_description}

## Target Label
{label}  <!-- "Entailment" or "Non-entailment" -->

## Legal Context
- Law: {law_name}
- Field: {field_of_law}
- Article: {article_number}, Clause: {clause_number}, Point: {point_number}

## Task
Generate ONE hypothesis following the specified rule and target label.
Output format (JSON):
{{
  "premise_parsing": {{
    "legal_subject": "...",
    "normative_action": "...",
    "conditions": "...",
    "scope": "..."
  }},
  "reasoning": "Brief chain-of-thought explaining why this label holds.",
  "hypothesis": "...",
  "label": "{label}"
}}
```

### Round-by-Round Prompt Evolution (from Table 5)

| Round | κ    | What Changed in the Prompt                                             |
|-------|------|------------------------------------------------------------------------|
| 1     | 0.67 | Basic instruction: "Given premise X, generate entailment/non-entailment hypothesis." No structure, no reasoning steps. |
| 2     | 0.80 | Added explicit inference constraints: "Entailment means logically derivable. Non-entailment means contradiction or unsupported." |
| 3     | 0.83 | Added artifact awareness: "Avoid words that reveal the label without reading the premise." Plus formal register instruction. |
| 4     | 0.85 | Introduced **causal and purposive reasoning** in the prompt: "Consider the purpose (purposive) and causal chain of the legal provision." |
| 5     | 0.85 | Added diversity instruction: "Vary sentence structure, legal scenarios, and reasoning patterns across generations." |
| 6     | 0.87 | Added **multi-clause legal reasoning**: "For complex premises with interdependent clauses, reason across the clause hierarchy before generating." |

---

## Adversarial Types for Hypothesis Generation

Based on the paper's 19 generation rules (Table 6) and error analysis (Table 16), each rule maps to an adversarial strategy. Organized by difficulty tier.

### Tier 1: Surface-Level Adversarial (Easy — Models Handle Well)

These are lexical/syntactic transformations. The paper's results show models achieve high accuracy (85-90%+) on these.

| Adversarial Type   | Rule | Technique                              | Example (VI)                                                                 |
|--------------------|------|----------------------------------------|------------------------------------------------------------------------------|
| **Voice Flip**     | E1   | Active ↔ passive, preserve semantics   | "A bị xử phạt" → "Xử phạt được áp dụng đối với A"                           |
| **Synonym Swap**   | E2   | Replace entity with legal synonym      | "Người chưa thành niên" → "Người dưới 18 tuổi"                              |
| **Clause Reform**  | E3   | Nominalization ↔ clausal form          | "Việc vi phạm..." → "Nếu có hành vi vi phạm..."                             |
| **Condition Flip** | E4   | Reformulate conditional, preserve logic| "Khi X thì Y" → "Y được áp dụng trong trường hợp X"                         |
| **Num Equivalence**| E5   | Equivalent numerical expression        | "Phạt 5-10 triệu" → "Phạt từ 5.000.000 đến 10.000.000 đồng"                 |

### Tier 2: Structural Adversarial (Medium — Models Partially Handle)

These require understanding logical structure. The paper shows accuracy drops ~5-10% on these.

| Adversarial Type       | Rule | Technique                                    | Example (VI)                                                                 |
|------------------------|------|----------------------------------------------|------------------------------------------------------------------------------|
| **Complexity Bomb**    | E6   | Expand sentence with subordinate clauses      | Add "theo quy định tại khoản..." clauses that don't change meaning           |
| **Logic Chain**        | E7   | Derive a non-obvious consequence             | From "cấm hành vi X" → "hành vi X là vi phạm pháp luật" (implicit consequence)|
| **Rule Narrowing**     | E8   | Apply broad rule to narrow specific case     | From "mọi công dân có quyền X" → "người dân tộc thiểu số có quyền X"        |
| **Cross-Reference**    | E9   | Link to semantically related clause          | Add reference to another clause that shares the same legal principle         |

### Tier 3: Deep Semantic Adversarial (Hard — Models Struggle)

These require genuine legal reasoning. The paper's error analysis (Table 16) shows these cause **22% false negatives** and **15% false positives**.

| Adversarial Type       | Rule  | Technique                                          | Error Rate |
|------------------------|-------|----------------------------------------------------|------------|
| **Negation Injection** | NE1   | Insert structural negation/contradiction           | 15% FPs    |
| **Entity Poison**      | NE2   | Swap legal subject, timeframe, or action scope     | —          |
| **Scope Distortion**   | NE3   | Create semantic inconsistency via scope widening   | —          |
| **Condition Sabotage** | NE4   | Add contradictory condition to premise logic       | —          |
| **Num Bait**           | NE5   | Change numerical threshold to invalidate premise   | —          |
| **Fake Reasoning**     | NE6   | Generate logically invalid but plausible-sounding inference | 22% FNs† |
| **Assumption Injection**| NE7  | Add unsupported assumption as if it were given     | 22% FNs†   |
| **Rule Hijack**        | NE8   | Apply correct rule to wrong case (overgeneralize)  | 13% FNs    |
| **Irrelevant Link**    | NE9   | Link to unrelated legal clause                     | —          |
| **Decoy Statement**    | NE10  | Create independent statement with high lexical overlap | —      |

† Error rates for E6+E7 combined (22%) and E8+E9 combined (13%) from Table 16.  
FPs = False Positives (model predicts entailment but correct label is non-entailment).  
FNs = False Negatives (model predicts non-entailment but correct label is entailment).

### Adversarial Difficulty Ladder (by Model Performance from Paper)

```
EASIEST ─────────────────────────────────────────────────────────────► HARDEST

E1, E2, E3      E4, E5, E6      E7, E8, E9      NE1, NE6, NE7     E8, E9
(Voice/Synonym)  (Condition/Num) (Logic/Ref)      (Negation/Fake)   (Multi-step
[≥90% acc]       [85-90% acc]    [80-85% acc]     [75-80% acc]      reasoning)
                                                                    [<75% acc]
```

### Implementation Priority for Synthetic Data Pipeline

When building the generator, implement rules in this order to maximize coverage vs. difficulty:

| Priority | Phase  | Rules                              | Rationale                                               |
|----------|--------|------------------------------------|---------------------------------------------------------|
| P0       | MVP    | E1, E2, NE1, NE2, NE10             | Covers basic entailment + non-entailment. Fast to ship. |
| P1       | V1     | E3, E4, E7, NE3, NE4, NE6          | Adds logical reasoning + contradiction types.           |
| P2       | V1.5   | E5, E6, NE5, NE7, NE8              | Adds numerical + assumption-based adversarial.          |
| P3       | V2     | E8, E9, NE8, NE9                   | Multi-clause cross-reference reasoning. Hardest tier.   |

### Adversarial Prompt Augmentation (for your Generator)

To generate harder adversarial examples, prepend these instructions to the system prompt:

```text
## Adversarial Augmentation Level: {level}

Level 1 — BASIC:
- Use surface transformations only (voice, synonyms, clause reform)

Level 2 — STRUCTURAL:
- Add subordinate clauses, cross-references, or scope modifiers
- Maintain grammatical correctness but increase sentence complexity

Level 3 — SEMANTIC:
- Require multi-step inference to determine the label
- Use implicit legal consequences rather than explicit statements
- Exploit legal ambiguities (e.g., "có thể" vs "phải")

Level 4 — ADVERSARIAL:
- Maximize lexical overlap between premise and hypothesis
  (target >60% Jaccard) while flipping the label
- Use high-PMI trigger words in WRONG label contexts
  (e.g., use "Theo quy định" in a Non-entailment hypothesis)
- Generate plausible-but-wrong legal reasoning chains
- Insert subtle scope or timeframe shifts that change meaning

## Anti-Artifact Constraint
Regardless of adversarial level, NEVER rely on these surface cues alone
to signal the label:
- Non-entailment cues: "Dù", "mặc dù", "không cần", "bất kể", "tự do"
- Entailment cues: "Khi", "Theo quy định", "căn cứ", "đồng thời"
If these words appear, they must be semantically justified by the premise,
not inserted as label shortcuts.
```

