# Validator Flow

Validator phase kiểm tra generated Vietnamese NLI rows theo sơ đồ 3 lớp
(`0=entailment`, `1=neutral`, `2=contradiction`) với expected label bị mask khỏi
validator. Có ba lớp: một **per-run** blind check do một model tạo ra (tính
`accepted` deterministic), một **cross-model consensus** gộp nhiều file verdict
per-run thành `decision` keep/review/discard, và một pass **artifact-flagging**
deterministic tìm các token làm lộ label. Trusted runtime canonicalize cả hai phía
(`src/utils/nli_labels.py: canonical_label`) để numeric expected label và string
predicted label so sánh đúng.

## State Machine

Lớp 1 — per-run blind check (một validator model). Đây là main run loop:

```text
┌──────────────────────────────────────────────────────────┐
│ read skills:                                             │
│ instructor · execution · progress_tracking · validator   │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ start_validation_run(from_sample, to_sample)             │
│ • .pipeline/validation/runs/{run_id}                     │
│ • data/batches/{run_id}                                  │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ claim_next_validation_batch                              │
│ → source_uid, premise, hypothesis,                       │
│   masked_label=[MASK]   (expected_label is hidden)       │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ validator predicts 3-class label                         │
│ entailment | neutral | contradiction                     │
│ + reason (Vietnamese)                                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ submit_validation_result            [deterministic]      │
│ runtime joins hidden expected_label, then computes       │
│ accepted = canonical(pred) == canonical(expected)        │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ claim loop                                               │
│ claimed  → predict & submit  (back to predict step)      │
│ waiting  → inspect / release abandoned claim             │
│ complete → verify_validation_progress_log                │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ finalize_validation_run                                  │
│ ok   → validation_results.csv ; run state wiped          │
│ fail → runtime artifacts kept for debugging              │
└──────────────────────────────────────────────────────────┘
```

Lớp 2 — cross-model consensus (offline, deterministic CLI). Chạy Lớp 1 một lần
cho mỗi model để có N file verdict, rồi aggregate:

```text
┌──────────────────────────────────────────────────────────┐
│ run Layer 1 once per model →  verdict files              │
│ gpt4o.csv · deepseek.csv · llama.csv · …                 │
│ (source_uid, predicted_label, reason)                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli aggregate                              │
│   --verdicts-dir  --masked-input  --expected-input       │
│ agree_count = #models canonical(pred)==canonical(exp)    │
└──────────────────────────────────────────────────────────┘
                              │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ KEEP             │   │ REVIEW           │   │ DISCARD          │
│ agree ≥ 2        │   │ agree == 1       │   │ agree == 0       │
└──────────────────┘   └──────────────────┘   └──────────────────┘

TẤT CẢ row → validation_votes.csv     (mọi row + decision keep/review/discard)
CHỈ KEEP   → validated_dataset.csv     (source_uid,premise,hypothesis,label)
CHỈ REVIEW → review_dataset.csv        (source_uid,premise,hypothesis + label từng
                                        model, expected_label, agree_count)
```

`review_dataset.csv` là hàng đợi manual review (agree == 1), giữ đầy đủ vote
context để người duyệt thấy chỗ bất đồng; `expected_label` được giữ nguyên (không
đổi thành `label`) vì các row này chưa được xác thực. PMI là bước riêng (Lớp 3
bên dưới), không phải output của aggregate.

Lớp 3 — artifact flagging (deterministic, corpus-level). Chạy trên các row
validated/kept:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli pmi                                    │
│   --input <validated_dataset.csv> --pmi-threshold T     │
│ PMI computed ONCE over all rows, example-level (Eq. 2)   │
│ default --label-column label                             │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ pmi_artifact_tokens.csv   → (token, label, pmi, …)       │
│ pmi_flagged_rows.csv      → hypotheses whose token       │
│                             leaks its own label          │
│                             → paraphrase these           │
└──────────────────────────────────────────────────────────┘
```

Lớp 4 — apply paraphrase (deterministic). Harness paraphrase các hypothesis
trong `pmi_flagged_rows.csv` (bước LLM, ngoài code), xuất file
`source_uid,hypothesis` đã viết lại, rồi apply ngược để khép stage:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli apply-paraphrase                       │
│   --input validated_dataset.csv                          │
│   --paraphrases <paraphrased.csv>                        │
│ Ghi đè hypothesis của các row flagged, giữ nguyên còn lại│
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   processed_dataset.csv  (source_uid,premise,hypothesis,label)
   → deliverable cuối của stage validation, sẵn sàng để split/train
```

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,masked_label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

## Per-run Final Output Schema

```csv
source_uid,premise,hypothesis,expected_label,predicted_label,accepted,reason
```

## Consensus Vote Table Schema

```csv
source_uid,<model>_label...,expected_label,agree_count,decision
```

## Ghi chú

- Chỉ dùng `premise`, `hypothesis`, và rubric; tuyệt đối không suy hidden label
  từ row order, metadata, batch id, hoặc prior outputs.
- Trả về một trong 3 canonical name (`entailment`|`neutral`|`contradiction`);
  runtime tự map sang numeric id. `reason` là tiếng Việt.
- `accepted` (per-run, một model) và `decision` (cross-model consensus) là hai lớp
  khác nhau: `accepted` = một model này có khớp `expected_label` không;
  `decision` = có >= 2 trong N model khớp `expected_label` không.
