### [2026-06-19 21:42] — [PromptRefinement] Add subagent orchestration templates

**Đã làm:**
- Added English and Vietnamese copy-paste templates for Codex to orchestrate exactly three isolated validator subagents.
- Defined main-agent ownership of MCP calls, prompt edits, verdict persistence, MLflow evaluation, and explicit locking.
- Defined subagent isolation: masked rows only, no expected labels, no cross-agent verdict sharing, no MCP or file mutation, and one real model path per subagent.
- Added retry/abort rules, prompt-freeze guards, round output paths, MLflow artifact retrieval, and regenerated-calibration hash caveats.
- Updated the refinement skill, instructor, validator flow docs, and README links.
- Verified `126 passed`, clean isort/black hooks, and `git diff --check`.

**Files thay đổi:**
- `backend/skills/prompt_refinement.md`, `backend/skills/instructor.md`
- `backend/tests/test_skill_service.py`
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md`
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md`
- `README.md`, `README.vi.md`

**Blockers:** None

**Còn lại:**
- The Codex harness still needs three genuinely independent model execution paths; three subagents using one underlying model are not valid three-model agreement.

**Flow explained:**
The Codex main agent freezes the calibration source UID set, generates or reuses the round input, dispatches three isolated model subagents in parallel, validates and writes one verdict file per model, then alone calls `evaluate_prompt_refinement_round`. Subagents never see expected labels, other verdicts, MCP state, or prompt files. Prompt files remain frozen from dispatch through evaluation; only the main agent may edit them after a `refine_prompt` result or confirm an unchanged eligible bundle.

---

### [2026-06-19 21:24] — [PromptRefinement] Add MLflow prompt calibration flow

**Đã làm:**
- Added an optional pre-generation refinement loop using one fixed calibration dataset and exactly three independent validator verdict files.
- Reused `compute_fleiss_kappa()` and exposed `evaluate_prompt_refinement_round` through the validation MCP provider.
- Registered generator and validator prompt snapshots in MLflow, logged kappa/label metrics and artifacts, assigned `candidate` aliases every round, and required explicit confirmation before assigning `locked`.
- Added `skill://prompt_refinement`, updated the instructor, and synchronized English/Vietnamese README, flow, and validator template docs.
- Verified a temporary SQLite MLflow store, MCP tool registration, `125 passed`, and clean isort/black pre-commit hooks.

**Files thay đổi:**
- `backend/src/services/prompt_refinement_service.py`, `backend/src/providers/validation_provider.py`, `backend/src/schemas/validation_runtime_schema.py`
- `backend/tests/test_prompt_refinement_service.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_skill_service.py`
- `backend/skills/prompt_refinement.md`, `backend/skills/instructor.md`
- `backend/pyproject.toml`, `backend/uv.lock`, `.gitignore`
- `README.md`, `README.vi.md`, `docs/en/flow/validator.md`, `docs/vi/flow/validator.md`
- `docs/en/template/validator.md`, `docs/vi/template/validator.md`

**Blockers:** None

**Còn lại:**
- The active agent harness must provide three real independent model execution paths; backend code intentionally does not call models or rewrite prompts automatically.

**Flow explained:**
Run MLflow separately only when calibration is needed. The agent reads `skill://prompt_refinement`, generates one fixed calibration sample, collects exactly three blind verdict files, then calls the MCP tool. Kappa below `0.85` returns `refine_prompt`; kappa at least `0.85` returns `eligible_to_lock`; only `confirm_lock=true` assigns the locked prompt aliases. PMI stays outside this loop and runs after large-scale generation and consensus validation.

---

### [2026-06-19 19:00] — [ValidationIntegrity] Harden validation pipeline integrity

**Đã làm:**
- Enforced the three-class label domain at runtime and offline aggregation boundaries; invalid source or predicted labels now fail before output is written.
- Required exactly three validator files, exact unique UID coverage across expected, masked, and verdict datasets, non-empty reasons, and collision-free normalized model names.
- Bound paraphrases to the exact PMI-flagged UID set; rejected missing/duplicate/null flag data, unchanged rewrites, and rewrites that retain listed artifact tokens.
- Renamed the post-rewrite candidate to `paraphrased_dataset.csv` and added `paraphrase_revalidation_masked.csv`; changed rows are not considered final until semantic revalidation.
- Built aggregate outputs fully before staging and replacing final CSV files, so validation/serialization failures do not truncate existing outputs.
- Updated English and Vietnamese validator flow docs. MCP wrappers and premise-grouped split remain intentionally deferred.
- Verified `118 passed` with `uv run pytest -q`; isort and black hooks pass; the four original repros now reject invalid input.

**Files thay đổi:**
- `backend/src/utils/nli_labels.py`, `backend/src/schemas/validation_runtime_schema.py`
- `backend/src/utils/validation_aggregation.py`, `backend/src/services/validation_run_service.py`, `backend/src/cli.py`
- `backend/tests/test_validation_aggregation.py`, `backend/tests/test_cli.py`
- `backend/tests/test_validation_run_service.py`, `backend/tests/test_validation_provider.py`
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md`

**Blockers:** None

**Còn lại:**
- Add thin MCP wrappers over the hardened deterministic functions.
- Operationalize semantic revalidation and promotion of paraphrased rows.
- Implement deterministic premise-grouped 8:1:1 split.

**Flow explained:**
Agent/LLM work remains semantic: produce verdicts or paraphrases. Python owns deterministic validation, aggregation, κ, PMI, and file application. The post-paraphrase dataset is a candidate plus an explicit masked revalidation queue, not a final training artifact.

---

### [2026-06-18 00:01] — Rewrite paper explanation as paper-only note

**What was done:**
- Pulled the ViLegalNLI paper context from arXiv and rewrote `docs/paper_explanation.md` as a standalone paper explanation.
- Removed repo/codebase comparison sections and replaced them with a full paper flow: task definition, seven-step dataset construction, prompt optimization, validation, PMI artifact mitigation, splitting, dataset analysis, experiments, result analysis, and conclusion.
- Clarified the important distinction: low κ belongs to prompt/data-construction calibration, while high PMI leads to paraphrasing hypothesis text.

**Files changed:**
- `docs/paper_explanation.md` — rewritten as paper-only explanation.
- `docs/PROGRESS.md` — added this progress entry.

**Blockers:**
- None.

**Remaining issues:**
- None known.

**Flow explained:**
`paper_explanation.md` now treats ViLegalNLI as the source of truth and avoids mixing in implementation status. The key mental model is: prompt optimization happens before large-scale generation and uses Fleiss' κ to calibrate generation/labeling prompt setup; data validation happens after generation and retains examples with at least two validating models agreeing with the original label; PMI/artifact mitigation happens after validation and paraphrases high-PMI hypotheses; benchmarking happens only after the final split.

---

### [2026-06-17 21:35] — Fix stale validator docs + add review_dataset.csv artifact

**What was done:**
- Removed stale `pmi_consensus.csv` references from `docs/en/flow/validator.md` and `docs/vi/flow/validator.md` (aggregate no longer writes it; PMI is the separate `cli pmi` step). Also corrected the misleading diagram label: `validation_votes.csv` holds ALL rows + decisions, `validated_dataset.csv` only the KEEP subset.
- Addressed the operational risk that REVIEW rows (agree==1) had no downstream artifact: `aggregate` now also writes `review_dataset.csv` (manual-review queue).

**Files changed:**
- `backend/src/utils/validation_aggregation.py` — extracted `_assert_masked_coverage()` helper (shared by retained + review builders); added `build_review_dataset()`.
- `backend/src/cli.py` — `run_aggregation()` writes `review_dataset.csv`; summary table + result dict report review rows/output; import added.
- `backend/tests/test_validation_aggregation.py` — added 2 tests for `build_review_dataset` (filter + coverage guard).
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — corrected aggregate outputs, documented review_dataset.csv.

**Blockers:**
- None.

**Remaining issues:**
- None known.

**Flow explained:**
`aggregate` now emits 3 files: `validation_votes.csv` (full vote table, every row + keep/review/discard decision), `validated_dataset.csv` (KEEP only, expected_label→label, publishable schema), and `review_dataset.csv` (REVIEW only — text joined onto vote rows, keeps per-model labels + expected_label + agree_count so a human can see disagreement; expected_label is NOT renamed since these rows are unverified). Both retained and review builders share `_assert_masked_coverage()`, which raises on any kept/review source_uid missing from — or duplicated in — masked_input, preventing silent row loss or one-to-many inflation in the inner join. PMI remains a separate `cli pmi` step on `validated_dataset.csv`; no `pmi_consensus.csv` is produced.

---

### [2026-06-17 21:32] — Re-check aggregation coverage and review artifact

**What was done:**
- Re-checked the current aggregation changes after the retained-row fix and review artifact addition.
- Confirmed old missing-UID repro now fails explicitly for both retained rows and review rows.
- Confirmed active validator flow docs no longer reference `pmi_consensus.csv`.
- Ran a smoke aggregate: it wrote `validation_votes.csv`, `validated_dataset.csv`, and `review_dataset.csv`; review output kept text plus per-model labels, `expected_label`, `agree_count`, and `decision`.
- Ran the backend unittest suite: 80 tests pass.

**Files changed:**
- `docs/PROGRESS.md` — added this re-check entry.

**Blockers:**
- None.

**Remaining issues:**
- Older append-only `docs/PROGRESS.md` entries still mention previous `pmi_consensus.csv` behavior as history; active flow docs and current code/tests no longer do.

**Flow explained:**
The current aggregate path is now coverage-guarded for both publishable kept rows and manual-review rows. Missing or duplicated masked `source_uid` values fail before output generation, preventing silent row loss or one-to-many join inflation. Aggregate currently emits all-row votes, keep-only validated data, and review-only manual queue; PMI remains a separate step on the validated data.

---

### [2026-06-17 21:19] — Verify retained dataset coverage fix

**What was done:**
- Reviewed the fix for `validated_dataset.csv` silently dropping kept rows when `masked_input` is incomplete.
- Confirmed `build_retained_dataset()` now validates every kept `source_uid` exists in the masked dataset before joining text.
- Confirmed duplicate masked `source_uid` values for kept rows now fail instead of duplicating or ambiguously joining output rows.
- Ran the old repro: it now raises `ValueError: Expected 2 kept rows, but masked dataset is missing 1 source_uid(s): row-2`.
- Ran the backend unittest suite: 78 tests pass.

**Files changed:**
- `docs/PROGRESS.md` — added this verification entry.

**Blockers:**
- None.

**Remaining issues:**
- Validator flow docs still mention `pmi_consensus.csv` as an aggregate output, while current code/tests say aggregate only writes `validation_votes.csv` and `validated_dataset.csv`.
- `review` consensus rows still do not have a dedicated downstream manual-review artifact.

**Flow explained:**
The retained dataset step now fails before writing if the keep set from `validation_votes.csv` cannot be fully joined back to `masked_input`. That changes the previous silent truncation failure mode into an explicit data-integrity error with the missing `source_uid` values listed.

---

### [2026-06-17 20:30] — Review current pipeline against project docs

**What was done:**
- Reviewed `README.md`, Vietnamese flow docs, latest `docs/PROGRESS.md`, and current backend pipeline implementation.
- Verified MCP generation/validation paths still match the documented state machine at a high level: start, claim, submit, verify/finalize, then cleanup successful run state and `data/batches/{run_id}`.
- Found one real aggregation correctness risk: `build_retained_dataset()` inner-joins kept vote rows with `masked_input`, so a wrong or incomplete masked file silently drops kept rows instead of failing.
- Found a docs contradiction: latest `docs/PROGRESS.md` says `aggregate` intentionally no longer writes `pmi_consensus.csv`, tests enforce that, but `docs/en/flow/validator.md` and `docs/vi/flow/validator.md` still list `pmi_consensus.csv` as an aggregate output.
- Ran backend unittest suite from the backend working directory and a focused repro for the retained-row drop.

**Files changed:**
- `docs/PROGRESS.md` — created this review entry.

**Blockers:**
- None.

**Remaining issues:**
- `backend/src/utils/validation_aggregation.py` should validate masked text coverage for all kept rows before writing `validated_dataset.csv`.
- `docs/en/flow/validator.md` and `docs/vi/flow/validator.md` should remove or relocate `pmi_consensus.csv` to match current code/tests.
- `review` consensus rows remain only in `validation_votes.csv`; there is still no dedicated downstream manual-review artifact.

**Flow explained:**
Current pipeline has two paths. MCP runtime handles generation and single-model blind validation with trusted hidden-label comparison and cleanup after verified finalize. Deterministic CLI handles `mask -> aggregate -> pmi -> apply-paraphrase`: `aggregate` should produce only `validation_votes.csv` and `validated_dataset.csv`; `pmi` then runs on `validated_dataset.csv`; `apply-paraphrase` writes `processed_dataset.csv`. The main correctness gap is that `validated_dataset.csv` can currently be smaller than the keep set if `masked_input` is incomplete, because the text join is not coverage-checked.

---

### [2026-06-17 10:00] — Bỏ PMI thừa khỏi aggregate; thêm Fleiss kappa + apply-paraphrase CLI

**What was done:**
- Xác định `cli aggregate` đang tính PMI hai lần trên cùng tập KEPT rows: một lần nội bộ (`pmi_consensus.csv`) và một lần qua `cli pmi`. Paper chỉ có một lần (Step 7 sau consensus). Bỏ PMI ra khỏi `run_aggregation()` — xoá `pmi_consensus.csv`, bỏ `--min-joint-count` khỏi aggregate parser, bỏ `compute_hypothesis_label_pmi` và `attach_masked_text` khỏi import cli.py.
- `aggregate` giờ chỉ xuất `validation_votes.csv` + `validated_dataset.csv`. PMI hoàn toàn là việc của `cli pmi`.
- Thêm `compute_fleiss_kappa` + `kappa` CLI command (đo inter-model agreement, target κ≥0.85 per paper §4.1.4).
- Thêm `build_retained_dataset`, `apply_paraphrases` + `apply-paraphrase` CLI command (Layer 4 — ghi đè hypothesis bị flag PMI bằng paraphrase, xuất `processed_dataset.csv`).
- Cập nhật tests: đổi tên `test_run_aggregation_writes_votes_and_pmi` → `test_run_aggregation_writes_votes_and_validated_dataset`, xoá `test_run_aggregation_pmi_filters_by_min_joint_count`, thêm tests cho kappa + apply-paraphrase. Assert `pmi_consensus.csv` KHÔNG tồn tại sau aggregate.
- 36 tests pass.

**Files changed:**
- `backend/src/cli.py` — bỏ PMI khỏi aggregate, thêm kappa + apply-paraphrase commands.
- `backend/src/utils/validation_aggregation.py` — thêm `compute_fleiss_kappa`, `build_retained_dataset`, `apply_paraphrases`.
- `backend/tests/test_cli.py` — cập nhật + thêm tests.
- `backend/tests/test_validation_aggregation.py` — thêm tests cho kappa + apply-paraphrase.
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md`, `docs/paper_explanation.md` — đồng bộ flow 4 layer.

**Blockers:**
- None.

**Remaining issues:**
- `review` rows (agree_count==1) nằm trong `validation_votes.csv` nhưng không có downstream handler — cần file riêng để escalate manual review.
- Một `validator.md` prompt dùng chung cho tất cả model; paper dùng per-model tuned prompt (κ≥0.85).
- Dataset split 8:1:1 grouped by premise chưa implement.

**Flow explained:**
Layer 2 (`aggregate`): 3 verdict files → vote table (agree_count = #model khớp expected_label) → keep/review/discard → `validated_dataset.csv` (chỉ KEEP, rename expected_label→label). Layer 3 (`pmi`): chạy 1 lần duy nhất trên `validated_dataset.csv` → `pmi_artifact_tokens.csv` + `pmi_flagged_rows.csv`. Layer 4 (`apply-paraphrase`): nhận paraphrase CSV từ harness → overwrite hypothesis → `processed_dataset.csv`.

---

### [2026-06-17 01:00] — PMI làm đúng quy trình paper (Eq. 2 example-level + fix default CLI)

**What was done:**
- Đọc lại paper ViLegalNLI (arXiv:2605.00116v1, §4.1.7 / Eq. 2, Table 13) → sửa PMI cho đúng **example-level**: `_count_token_label_cooccurrence` giờ đếm token theo *presence* (1 lần/hypothesis) và `label`/tổng theo **số example** (trước đây đếm theo token-occurrence → `P(y)` bị nhân trọng số độ dài câu, sai Eq. 2). `compute_hypothesis_label_pmi` chuẩn hoá theo `n_examples`.
- Thêm test phân biệt example-level vs occurrence-level (token lặp trong 1 hypothesis → `token_count==1`, `joint_count==1`, `pmi==log2`).
- Fix bug default CLI: lệnh `pmi` đổi `--label-column` default `expected_label` → **`label`** cho khớp `validated_dataset.csv` (input thật của Step 7). Trước đó chạy luồng tài liệu với default sẽ lỗi "missing column expected_label".
- Cập nhật fixture test `pmi` (cột `label`), docs flow (en/vi) + paper_explanation.
- Suite: 77 passed (76 + 1 test mới); pre-commit sạch.

**Files changed:**
- `backend/src/utils/validation_aggregation.py` — `_count_token_label_cooccurrence` + `compute_hypothesis_label_pmi` về example-level (Eq. 2).
- `backend/src/cli.py` — `pmi --label-column` default `label` + help text.
- `backend/tests/test_validation_aggregation.py` — test example-level mới (+ import math).
- `backend/tests/test_cli.py` — fixture `pmi` dùng cột `label`.
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md`, `docs/paper_explanation.md` — đồng bộ mô tả PMI example-level + default label-column.

**Blockers:**
- None.

**Remaining issues:**
- **②** (gộp 1 bước PMI) **cố ý KHÔNG làm**: `aggregate` vẫn xuất `pmi_consensus.csv` (bảng chẩn đoán trên kept-set) — không sai paper, xoá sẽ phá hợp đồng/test/docs (surgical + YAGNI). Sửa ① đã làm PMI ở cả 2 chỗ đúng vì dùng chung hàm.
- Ngưỡng PMI: paper không nêu cutoff số; Table 13 ~0.80–0.99. Default CLI vẫn `1.0` — để tunable, chưa đổi.
- Cần confirm 1 câu trong §Step 7 về "PMI chạy trên tập validated hay full" (2 nguồn lệch); hiện theo bản verify = tập validated, khớp pipeline `validated_dataset.csv → pmi`.

**Flow explained:**
PMI Step 7 giờ trung thành Eq. 2: với mỗi example lấy `set(token)` của hypothesis, đếm `token_doc`, `label_doc`, `joint_doc` theo example, `N`=số example; `PMI(w,y)=log( joint·N / (token_doc·label_doc) )`. Cột `token_count/label_count/joint_count` trong output giờ mang nghĩa **đếm theo example**. Luồng vận hành không đổi (`mask → aggregate → pmi → apply-paraphrase`), chỉ default `--label-column` của `pmi` đổi sang `label` để chạy thẳng trên `validated_dataset.csv`.
