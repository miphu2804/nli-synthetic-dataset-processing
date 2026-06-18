# ViLegalNLI — Paper Explanation

Reference: *ViLegalNLI: Natural Language Inference for Vietnamese Legal Texts*,
Nhung Thi-Hong Duong, Mai Ngoc Ho, Tin Van Huynh, Kiet Van Nguyen
(arXiv:2605.00116v1, 30 Apr 2026). https://arxiv.org/abs/2605.00116v1

This note explains the paper itself. It intentionally stays focused on the
paper.

---

## 1. Paper goal

ViLegalNLI introduces a Vietnamese legal Natural Language Inference dataset. Each
example is a pair:

```text
premise:    a legal statement extracted from Vietnamese statutory text
hypothesis: a generated legal claim to test against the premise
label:      whether the hypothesis follows from the premise
```

The paper's task is **binary NLI**:

| Label | Meaning |
|---|---|
| `1` Entailment | The hypothesis can be logically inferred from the premise, or is semantically equivalent in the legal context. |
| `0` Non-entailment | The hypothesis cannot be inferred from the premise. This includes contradiction, semantic inconsistency, and insufficient legal support. |

The main contribution is not a new model architecture. The contribution is a
large Vietnamese legal NLI benchmark plus a semi-automatic construction pipeline
that tries to control label quality, lexical artifacts, and evaluation leakage.

Key dataset facts:

| Item | Value |
|---|---:|
| Active statutory documents | 168 |
| Extracted premises | 20,860 |
| Final premise-hypothesis pairs | 42,012 |
| Legal sub-domains | 27 |
| Train / dev / test | 34,121 / 4,160 / 3,731 |

---

## 2. Why legal NLI is hard

General NLI asks whether one sentence follows from another. Legal NLI is harder
because legal text often contains:

- hierarchical references: article, clause, point, chapter;
- conditional logic: if, unless, except, when, after;
- domain-specific terms whose meaning is fixed by law;
- enumerations where one missing condition changes the inference;
- implicit legal consequences that are not worded as ordinary paraphrases.

So a model cannot rely only on word overlap. It must decide whether the claim is
legally supported by the premise.

Example flow:

```text
Premise says:
A person from 16 to under 18 who commits a less serious crime may receive reprimand.

Entailment hypothesis:
A 17-year-old who commits a less serious crime may receive reprimand.

Non-entailment hypothesis:
A person of any age who commits any crime must receive reprimand.
```

The second hypothesis shares many words with the premise, but changes the legal
conditions. That is the type of distinction the dataset targets.

---

## 3. Dataset construction pipeline

The paper's Figure 2 describes seven steps:

```text
1. Data Collection
2. Data Preprocessing
3. Premise Extraction
4. Prompt Optimization and Labeling
5. Hypothesis Generation
6. Data Validation
7. Data Difficulty Evaluation
```

The important point: **prompt optimization, validation, and PMI are three
different stages**. They should not be collapsed into one mental bucket.

---

## 4. Step 1 — Data Collection

The authors crawl Vietnamese statutory documents from LuatVietnam. They choose
this source because it has broad coverage, structured document organization, and
regular updates.

Raw collection result:

```text
514 statutory documents
```

These are not all directly used. The paper later filters to documents currently
in force.

---

## 5. Step 2 — Data Preprocessing

The authors manually remove documents that are no longer effective. The active
legal corpus becomes:

```text
168 currently-in-force statutory documents
```

They also normalize the text by removing noise such as:

- decorative separators: `-----`, `_____`, `*****`, `=====`;
- redundant whitespace;
- administrative signatures and confirmation statements.

Purpose: the model should learn legal reasoning, not formatting artifacts.

---

## 6. Step 3 — Premise Extraction

The paper extracts premises from articles, clauses, and points. A premise is a
semantically complete legal statement that can support or reject a hypothesis.

The extraction is rule-based. The paper uses Vietnamese keyword indicators such
as:

| Indicator type | Examples | Typical position |
|---|---|---|
| enumerating phrases | `sau đây`, `như sau`, `bao gồm` | often near article end |
| prohibitive / sanction phrases | `nghiêm cấm`, `cấm`, `vi phạm`, `bị xử phạt`, `không được` | inside article |
| procedure phrases | `Thủ tục`, `Trình tự` | inside article |

Output:

```text
20,860 premises
```

Each dataset row keeps metadata for traceability: law ID, law name, date, legal
field, chapter, section, article, clause, point, premise, hypothesis, and label.

---

## 7. Step 4 — Prompt Optimization and Labeling

This is the part that caused confusion, so the distinction matters.

The paper uses:

| Role | Model(s) | Purpose |
|---|---|---|
| hypothesis generator | Gemini-2.5 Flash | generate candidate hypotheses under Entailment / Non-entailment |
| cross-model labelers | GPT-4o, DeepSeek-R1, LLaMA-4 Scout | independently label / check generated samples |

The paper says prompt design is important for two things:

1. **hypothesis quality** — Gemini must generate clear, legally consistent
   hypotheses;
2. **label consistency** — the labeling models should agree when the relation is
   clear.

The refinement loop is:

```text
write prompt version
        |
        v
generate / label 50 samples
        |
        v
measure inter-model agreement with Fleiss' kappa
        |
        v
inspect linguistic clarity and agreement errors
        |
        v
refine prompt configuration
        |
        v
repeat for 6 rounds
```

Table 5 shows Fleiss' kappa improving across rounds:

| Round | Kappa | Main improvement |
|---:|---:|---|
| 1 | 0.67 | basic prompt, ambiguous hypotheses |
| 2 | 0.80 | clearer inference constraints |
| 3 | 0.83 | reduced linguistic ambiguity |
| 4 | 0.85 | causal and purposive reasoning |
| 5 | 0.85 | more diverse legal scenarios |
| 6 | 0.87 | multi-clause legal reasoning |

The paper selects prompt configurations with near-perfect agreement
(`κ >= 0.85`) for large-scale data generation.

Important interpretation:

```text
Kappa is not a PMI score.
Kappa measures agreement between labeling models.
Low kappa means the prompt/data construction setup is producing ambiguity or inconsistent labels.
```

Prompt refinement here is broader than "validator prompt". It covers the
construction prompt setup: Gemini's generation prompt plus the independent
labeling prompts used to judge consistency.

---

## 8. Step 5 — Hypothesis Generation

After prompt refinement, Gemini-2.5 Flash generates hypotheses using the final
prompt and a predefined rule catalog.

The paper separates generation rules into two groups.

Entailment rules include:

| ID | Rule idea |
|---:|---|
| 1 | active-passive transformation with meaning preserved |
| 2 | replace entities with synonymous legal references |
| 3 | nominal-clausal reformulation |
| 4 | conditional reformulation preserving logic |
| 5 | equivalent numerical modification |
| 6 | sentence complexity expansion without meaning change |
| 7 | logical consequence inference |
| 8 | general-to-specific rule application |
| 9 | link to related clauses without changing meaning |

Non-entailment rules include:

| ID | Rule idea |
|---:|---|
| 1 | structural transformation introducing contradiction |
| 2 | alter entities, time, or actions |
| 3 | create semantic inconsistency |
| 4 | add contradictory conditions |
| 5 | modify numerical values |
| 6 | generate invalid reasoning statements |
| 7 | introduce unsupported assumptions |
| 8 | misapply general legal rules |
| 9 | link to unrelated clauses |
| 10 | create independent, non-inferable statements |

This is controlled generation. The goal is not just to create fluent Vietnamese.
The generated hypothesis must follow a known inference relation and reasoning
pattern.

---

## 9. Step 6 — Data Validation

After large-scale generation, the paper validates the generated labels.

The validation setup:

```text
Generated dataset from Gemini
        |
        v
hide original labels from validators
        |
        v
GPT-4o, DeepSeek-R1, LLaMA-4 Scout re-annotate every example independently
        |
        v
compare their labels with Gemini's original label
        |
        v
retain / manual-review / discard
```

The rules:

| Agreement with original label | Decision |
|---:|---|
| 3 of 3 | retain |
| 2 of 3 | retain |
| 1 of 3 | manual review |
| 0 of 3 | discard |

The paper reports:

| Label | Full 3-model agreement | At least 2-model agreement | Disagreement bucket |
|---|---:|---:|---:|
| Non-entailment | 93.28% | 98.81% | 1.19% |
| Entailment | 62.44% | 84.75% | 15.25% |
| Total | 79.34% | 92.45% | 7.55% |

Interpretation:

- Non-entailment is easier for models to agree on.
- Entailment is harder because it requires precise legal support, not just
  absence of contradiction.
- Validation is a label-quality filter, not the same thing as PMI artifact
  detection.

---

## 10. Step 7 — Data Difficulty Evaluation and Artifact Mitigation

After label validation, the paper checks whether the dataset has superficial
label cues.

First, it trains/evaluates a hypothesis-only diagnostic model. The premise is
removed. If a model still performs very well from the hypothesis alone, the
dataset probably contains label-correlated artifacts.

CafeBERT hypothesis-only result before mitigation:

| Split | Accuracy | F1 |
|---|---:|---:|
| Dev | 89.91 | 89.78 |
| Test | 88.63 | 88.50 |

That is high, so the paper computes PMI between hypothesis tokens and labels.

PMI idea:

```text
PMI(token, label) is high when a token appears with a label more often than expected by chance.
```

If token `Khi` appears disproportionately in entailment examples, it becomes a
label cue. If token `Dù` appears disproportionately in non-entailment examples,
it also becomes a cue.

Top artifact examples reported by the paper:

| Token / expression | Associated label | PMI | Frequency |
|---|---|---:|---:|
| `không cần` | Non-entailment | 0.95 | 13.02% |
| `Dù` | Non-entailment | 0.97 | 8.15% |
| `bất kể` | Non-entailment | 0.89 | 4.26% |
| `chỉ cần` | Non-entailment | 0.91 | 3.70% |
| `Khi` | Entailment | 0.99 | 5.52% |
| `Theo quy định` | Entailment | 0.98 | 5.44% |

Mitigation:

```text
high-PMI token found
        |
        v
find instances containing that label-indicative token
        |
        v
generative model rewrites the hypothesis
        |
        v
semantic meaning should be preserved, but artifact cue removed
```

Important interpretation:

```text
PMI high -> paraphrase the hypothesis text.
PMI high -> not prompt refinement.
```

The paper verifies paraphrase quality with cosine similarity between original
and revised hypotheses:

```text
average cosine similarity = 0.883
55.5% of revised instances exceed 0.9
```

Lower similarity is attributed to controlled logical transformations such as
negation or scope changes, not necessarily accidental semantic drift.

---

## 11. Dataset splitting

After validation and artifact mitigation, the dataset is split into train, dev,
and test with an 8:1:1 ratio.

Key anti-leakage rule:

```text
All hypotheses derived from the same premise must stay in the same split.
```

This prevents the model from seeing a premise during training and then being
evaluated on another hypothesis from the same premise.

Final split sizes:

| Split | Instances |
|---|---:|
| Train | 34,121 |
| Dev | 4,160 |
| Test | 3,731 |
| Total | 42,012 |

The paper also controls label and legal sub-domain distributions across splits.

---

## 12. Dataset analysis

The paper analyzes the resulting dataset along several dimensions.

### 12.1 Domain coverage

The dataset covers 27 legal sub-domains, including administrative organization,
state finance, culture-society, natural resources-environment, real estate,
commercial law, tax-fees, transportation, labor-wages, IT, investment,
enterprise, civil rights, banking, legal services, insurance, procedural law,
criminal liability, intellectual property, securities, and others.

The distribution is not uniform. Some domains have more legal provisions and
therefore more examples. The paper treats this as reflecting regulatory density,
not necessarily a dataset bug.

### 12.2 Sentence length

Average lengths:

| Text | Average tokens |
|---|---:|
| premise | 43.08 |
| hypothesis | 43.74 |

Premises have a long tail beyond 200 tokens. Hypotheses are more concentrated
around 25-60 tokens. The intended effect is that hypotheses are concise legal
claims derived from longer statutory text.

### 12.3 Lexical overlap

The paper measures Jaccard similarity, LCS, and new-word rate.

| Label | Jaccard | LCS | New-word rate |
|---|---:|---:|---:|
| Entailment | 28.71% | 41.34% | 60.00% |
| Non-entailment | 18.43% | 34.29% | 75.39% |

Entailment has higher overlap on average, but both classes include substantial
new words. This supports the claim that hypotheses are not just copied from
premises.

### 12.4 Generation-rule distribution

The paper checks whether generation rules themselves leak the label. Some rules
are more common for one label, but no rule is exclusive to a single label. This
is meant to reduce rule-based annotation artifacts.

---

## 13. Experimental methodology

The paper evaluates several model groups.

| Group | Models |
|---|---|
| Multilingual encoders | mBERT, XLM-R base/large, InfoXLM base/large |
| Vietnamese monolingual encoders | PhoBERT base/large, viBERT, CafeBERT |
| Improved transformer encoders | DeBERTa V3 base/large |
| LLMs | Gemma-3, Qwen2.5, Gemma-2 |

Training setup for fine-tuned models:

| Setting | Value |
|---|---:|
| optimizer | Adam |
| learning rate | 1e-5 |
| train batch size | 16 |
| eval batch size | 32 |
| gradient accumulation | 2 |
| epochs | 5 |
| weight decay | 0.01 |
| precision | FP16 |

Metrics:

- Accuracy;
- macro-F1 over Entailment and Non-entailment.

Macro-F1 matters because a model can look good on accuracy while being biased
toward the easier class.

---

## 14. Main experimental results

Table 14 reports dev/test accuracy and F1.

Best result:

| Model | Setting | Test accuracy | Test F1 |
|---|---|---:|---:|
| Qwen2.5 | few-shot prompting | 90.72 | 90.64 |

Other notable results:

| Model | Test accuracy | Test F1 |
|---|---:|---:|
| Gemma-3 few-shot | 88.92 | 88.86 |
| InfoXLM large | 87.98 | 87.85 |
| CafeBERT | 87.49 | 87.36 |
| XLM-R large | 86.37 | 86.19 |
| Gemma-2 fine-tuned | 83.74 | 81.80 |
| Qwen2.5 zero-shot | 79.62 | 77.83 |

Interpretation:

- Few-shot LLMs perform best.
- Domain-adapted and multilingual encoders are strong baselines.
- Zero-shot LLMs are weaker than few-shot LLMs, showing that task guidance
  matters.
- Fine-tuning a compact LLM helps, but does not beat few-shot Qwen2.5.

---

## 15. Result analysis

### 15.1 Hypothesis length

Models perform poorly on very short hypotheses because there is not enough legal
context. Performance improves for medium-length hypotheses, then stabilizes or
slightly declines for very long hypotheses.

Practical reading:

```text
too short -> under-specified legal claim
too long  -> noisy / complex claim
medium    -> enough information without excess noise
```

### 15.2 Lexical overlap

Accuracy does not increase monotonically with word overlap. Moderate overlap is
helpful; very high overlap can mislead smaller pretrained models into predicting
entailment from surface similarity.

The paper also analyzes LCS and new-word rate. Instruction-tuned LLMs are more
stable when overlap is low or new-word rate is higher, suggesting better semantic
rather than purely lexical reasoning.

### 15.3 Label difficulty

Most models perform better on Non-entailment than Entailment.

Reason: Non-entailment often contains a clearer deviation, contradiction, or
unsupported assumption. Entailment requires proving that all legal conditions in
the hypothesis are supported by the premise.

### 15.4 Legal sub-domain difficulty

Performance varies by domain. More standardized domains such as civil, criminal,
and administrative law tend to be easier. Technical domains such as finance,
taxation, securities, and intellectual property are harder because they contain
specialized terminology and domain-specific reasoning.

### 15.5 Generation-rule difficulty

For Entailment, rules involving direct meaning-preserving transformations are
easier. Rules requiring implicit legal consequence, general-to-specific
application, or linking related clauses are harder.

For Non-entailment, models are generally stronger when the hypothesis clearly
deviates from the premise. Subtle logical inconsistency remains difficult.

### 15.6 Cross-domain evaluation

The paper compares in-domain and cross-domain results for XLM-R large and
CafeBERT. Performance degradation is small; in some reported scores,
cross-domain performance is slightly higher.

The authors interpret this as evidence that the models capture some general legal
reasoning patterns, but they also caution that deeper legal inference remains
challenging.

### 15.7 Error analysis

Major error types:

| Type | Pattern | Description | Rate |
|---|---|---|---:|
| 1 | Entailment -> Non-entailment | fails to recognize implied clauses and legal consequences, especially Entailment Rules 6 and 7 | 22% |
| 2 | Non-entailment -> Entailment | misled by lexical overlap, especially Non-entailment Rule 1 | 15% |
| 3 | Entailment -> Non-entailment | fails at general-to-specific reasoning or combining related legal provisions, Entailment Rules 8 and 9 | 13% |
| 4 | model-specific bias | predicts Non-entailment when sentence meaning is uncertain | 37% |

The strongest conceptual takeaway: current models still struggle with implicit,
multi-step, and cross-clause legal reasoning.

---

## 16. Clean mental model

Use this separation:

```text
Prompt optimization / kappa
    happens before large-scale generation
    measures inter-model label agreement on sample rounds
    refines generation + labeling prompt configuration

Data validation
    happens after large-scale generation
    hides original labels from three models
    keeps examples if at least two models agree with the original label

PMI / artifact mitigation
    happens after validation
    detects label-correlated tokens in hypotheses
    paraphrases affected hypotheses to remove lexical cues

Benchmarking
    happens after the final dataset is split
    compares encoders and LLMs on Accuracy and macro-F1
```

Short version:

```text
kappa low  -> refine prompt setup
PMI high   -> paraphrase hypothesis text
low score  -> model has reasoning weakness, especially on entailment and multi-step legal logic
```

---

## 17. Paper's conclusion

ViLegalNLI provides the first large-scale Vietnamese legal NLI benchmark. It is
built from statutory documents, generated with LLM assistance, filtered by
cross-model validation, and cleaned for lexical artifacts.

The experiments show that few-shot LLMs are strong, but the dataset remains
challenging. The hard cases are not ordinary paraphrase matching; they involve
implicit legal consequence, multi-clause reasoning, low lexical overlap, and
specialized legal domains.

Future work proposed by the authors includes expanding to more legal document
types and modeling more complex inference phenomena such as multi-step reasoning,
exception handling, cross-article dependencies, and paragraph/document-level
inference.
