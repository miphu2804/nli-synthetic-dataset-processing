# Validator Flow

Validator phase kiểm tra generated Vietnamese NLI rows theo sơ đồ 3 class
(`0=entailment`, `1=neutral`, `2=contradiction`) với expected label bị mask khỏi
validator. **Lớp 0** tùy chọn calibrate generator và validator prompt trước
large-scale generation. Corpus sau đó đi qua bốn lớp: blind validation per-run,
cross-model consensus, artifact flagging, và apply paraphrase kèm semantic
revalidation. Trusted runtime validate và normalize chặt chẽ cả hai phía
(`src/utils/nli_labels.py: require_supported_nli_label`) — chỉ chấp nhận `0/1/2` và
các supported label name `entailment`/`neutral`/`contradiction`; giá trị khác đều raise
trước khi ghi output.

## State Machine

Lớp 0 — prompt refinement tùy chọn trước large-scale generation:

```text
fixed labeled calibration dataset
  -> generate bằng generator policy đã chọn
  -> đúng ba validator độc lập chấm cùng các row
  -> evaluate_prompt_refinement_round
  -> kappa < 0.85: prepare_prompt_refinement_evidence_pack
  -> orchestrator spawn editor subagents bằng static editor templates
  -> sửa prompt
  -> kappa >= 0.85: eligible_to_lock
  -> confirm_prompt_lock: lock prompt bundle sau approval
  -> bắt đầu large-scale generation
```

MLflow được operator chạy riêng; backend không tự khởi động MLflow. Mỗi round
ghi prompt versions, Fleiss' kappa, verdict files, disagreements, và bundle
decision. Giữ cố định source UID set giữa các round bằng quy ước operator khi
các round cần so sánh trực tiếp. Nếu generator policy đã chọn đổi, regenerate
đúng UID set đó; nếu chỉ validator prompt đổi, reuse generated calibration file. Đọc
`skill://prompt_refinement` để chạy đúng flow.

Codex main agent sở hữu MCP calls, prompt edits, và file persistence. Main agent
dispatch ba validator subagent cô lập; mỗi subagent chỉ nhận masked rows và trả
verdict mà không đọc expected label hoặc output của model khác.
Prompt file phải giữ nguyên từ lúc dispatch đến khi MCP evaluation hoàn tất.

PMI không phải trigger sửa prompt. PMI thuộc Lớp 3 sau generation và consensus
validation.

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
│   label=""   (expected_label is hidden)                  │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ validator predicts 3-class label                         │
│ entailment | neutral | contradiction  (hoặc 0 | 1 | 2)  │
│ + reason (tiếng Việt, không được để trống)               │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ submit_validation_result            [deterministic]      │
│ predicted_label được validate tại schema boundary;       │
│ runtime join hidden expected_label, tính                 │
│ accepted = normalize(pred) == normalize(expected)        │
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

Lớp 2 — cross-model consensus (offline, deterministic CLI). Chạy Lớp 1 **đúng
ba lần** (mỗi model một lần) để có đúng ba file verdict, rồi aggregate. Pipeline
thực hiện quy tắc `2 trong 3` theo paper; CLI enforce đúng ba file và reject nếu
nhiều hơn hoặc ít hơn.

**Điều kiện đầu vào:**
- Đúng ba file verdict (gpt4o.csv, deepseek.csv, llama.csv hoặc tên tương đương).
- Mỗi file: `source_uid, predicted_label, reason` — không null UID, không
  duplicate UID, reason không được trống, label phải thuộc 3-class domain.
- Cả ba file phải có cùng tập `source_uid` chính xác.
- Dataset expected-label phải có cùng tập `source_uid` chính xác.
- Dataset masked phải có cùng tập `source_uid` chính xác.
- Bất kỳ mismatch nào đều raise trước khi ghi output (output được staged, rồi
  mới thay thế file cũ — validation failure không bao giờ truncate file hiện có).

```text
┌──────────────────────────────────────────────────────────┐
│ chạy Lớp 1 đúng một lần cho mỗi model → verdict files   │
│ gpt4o.csv · deepseek.csv · llama.csv                     │
│ (source_uid, predicted_label, reason)                    │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli aggregate                              │
│   --verdicts-dir  --masked-input  --expected-input       │
│ agree_count = #model có normalize(pred)==normalize(exp)  │
└──────────────────────────────────────────────────────────┘
                              │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ KEEP             │   │ REVIEW           │   │ DISCARD          │
│ agree ≥ 2 / 3    │   │ agree == 1       │   │ agree == 0       │
└──────────────────┘   └──────────────────┘   └──────────────────┘

TẤT CẢ row → validation_votes.csv    (mọi row + decision keep/review/discard)
CHỈ KEEP   → validated_dataset.csv   (source_uid,premise,hypothesis,label)
CHỈ REVIEW → review_dataset.csv      (source_uid,premise,hypothesis + label từng
                                       model, expected_label, agree_count)
```

`review_dataset.csv` là hàng đợi manual review (agree == 1), giữ đầy đủ vote
context để người duyệt thấy chỗ bất đồng; `expected_label` được giữ nguyên
(không đổi thành `label`) vì các row này chưa được xác thực và không được publish
như vậy. `accepted` (flag per-model ở Lớp 1) và `decision` (cross-model consensus)
là hai lớp khác nhau.

Operator có thể chạy layer này bằng CLI `aggregate`. MCP chỉ expose wrapper
cho combined stage `run_consensus_pmi` sau khi aggregate + PMI được chạy như
một contract ổn định.

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
│ pmi_flagged_rows.csv      → các row có hypothesis lộ     │
│                             label qua token              │
│                             → cần paraphrase             │
└──────────────────────────────────────────────────────────┘
```

Operator có thể chạy Lớp 2 + Lớp 3 bằng một command để persist đủ artifact vào
một thư mục chuẩn:

```bash
python -m src.cli consensus-pmi \
  --verdicts-dir <verdicts_dir> \
  --masked-input <validation_masked.csv> \
  --expected-input <labeled_dataset.csv> \
  --output-dir data/validated/<run_or_dataset_id> \
  --yes
```

Nếu bỏ `--output-dir`, default là `data/validated/<expected-input-stem>`.
MCP wrapper tương đương là `run_consensus_pmi`; wrapper này vẫn deterministic,
không gọi model, và ghi cùng bộ artifact vào cùng output convention.

Lớp 4 — apply paraphrase (deterministic). Harness paraphrase các hypothesis trong
`pmi_flagged_rows.csv` (bước LLM, ngoài code), xuất file `source_uid,hypothesis`
đã viết lại, rồi apply ngược:

**Điều kiện đầu vào:**
- `--flagged-rows pmi_flagged_rows.csv` là bắt buộc; không tự suy flagged rows
  từ paraphrase file.
- Tập UID flagged phải bằng tập UID paraphrase chính xác.
- Mỗi rewrite phải khác rỗng, khác bản gốc, và không còn chứa token nào trong
  cột `artifact_tokens` của row đó.

**Output:**
- `paraphrased_dataset.csv` — dataset candidate với rewrite đã apply. **Chưa
  phải final.** Semantic label của các row đã thay đổi phải được revalidate trước
  khi publish.
- `paraphrase_revalidation_masked.csv` — hàng đợi revalidation, chỉ chứa các row
  đã thay đổi: `source_uid, premise, hypothesis, label=""`.

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli apply-paraphrase                       │
│   --input validated_dataset.csv                          │
│   --flagged-rows pmi_flagged_rows.csv                    │
│   --paraphrases <paraphrased.csv>                        │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   paraphrased_dataset.csv           (candidate — chờ revalidate)
   paraphrase_revalidation_masked.csv (changed-row revalidation queue)
```

Lớp 5 — promote paraphrase sau semantic revalidation. Chạy đúng ba validator
trên `paraphrase_revalidation_masked.csv`, mỗi model xuất một verdict file
`source_uid,predicted_label,reason`. Sau đó dùng trusted labels để promote chỉ
các rewrite còn giữ đúng label theo quy tắc `2 trong 3`:

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli promote-paraphrase                     │
│   --input paraphrased_dataset.csv                        │
│   --revalidation-input paraphrase_revalidation_masked.csv │
│   --verdicts-dir <revalidation_verdicts_dir>              │
│   --expected-input validated_dataset.csv                  │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   promoted_dataset.csv                 (publishable candidate)
   paraphrase_revalidation_votes.csv    (all changed rows + decisions)
   paraphrase_revalidation_review.csv   (review/discard changed rows)
```

`promoted_dataset.csv` giữ các row không đổi và các rewrite được revalidation
`keep`. Rewrite có decision `review` hoặc `discard` bị loại khỏi publishable
output và được ghi vào review artifact.
MCP wrapper tương đương là `promote_paraphrase_revalidation`; wrapper này chỉ
gọi cùng logic deterministic của CLI và yêu cầu đúng ba verdict files.

Lớp 6 — final grouped-stratified split với premise anti-leakage. Chỉ chạy sau
khi đã có dataset final publishable, thường là `promoted_dataset.csv` nếu
PMI/paraphrase có rewrite, hoặc `validated_dataset.csv` nếu không có row nào
cần paraphrase. Split giữ mọi hypothesis cùng `premise` trong cùng một tập để
tránh leakage giữa train/dev/test, rồi greedy cân bằng row counts và label
distribution. Nếu có cột domain/subdomain thì có thể truyền thêm để giữ cả
distribution đó.

```text
┌──────────────────────────────────────────────────────────┐
│ python -m src.cli split                                  │
│   --input promoted_dataset.csv                           │
│   --output-dir data/splits/<run_or_dataset_id>            │
│   --group-column premise                                 │
│   --domain-column subdomain   # optional                 │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
   train.csv
   dev.csv
   test.csv
   split_manifest.json  (strategy, seed, ratios, row/group counts,
                         label distribution, optional domain status/distribution)
```

Default ratio là `0.8/0.1/0.1`, seed default `13`, và strategy mặc định là
grouped-stratified. Có thể override bằng `--train-ratio`, `--dev-ratio`,
`--test-ratio`, và `--seed`; tổng ratio phải bằng `1.0`.

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

`predicted_label` phải là một trong `entailment`, `neutral`, `contradiction`, `0`,
`1`, hoặc `2`. Bất kỳ giá trị nào khác đều bị reject tại schema validation trước
khi batch được ghi.

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
- Trả về một trong 3 supported label name (`entailment`|`neutral`|`contradiction`);
  runtime tự map sang numeric id. `reason` là tiếng Việt và không được để trống.
- `accepted` (per-run, một model) và `decision` (cross-model consensus) là hai lớp
  khác nhau: `accepted` = một model này có khớp `expected_label` không; `decision`
  = có ≥ 2 trong 3 model khớp `expected_label` không.
- Kappa cho prompt calibration đã có qua
  `evaluate_prompt_refinement_round` và được log vào MLflow. Các CLI stage
  deterministic `aggregate`, `pmi`, và `apply-paraphrase` vẫn do operator chạy.
  Hai combined/stable stages `consensus-pmi` và `promote-paraphrase` cũng có
  MCP wrappers mỏng: `run_consensus_pmi` và
  `promote_paraphrase_revalidation`.
