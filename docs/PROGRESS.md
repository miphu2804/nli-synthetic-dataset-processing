### [2026-06-28 01:00] — [PostValidation] Move phase logic into services

**Đã làm:**
- Tạo package `backend/src/services/post_validation/` cho các phase sau validation: aggregation, artifact detection, paraphrase, và dataset split.
- Đổi CLI và validation MCP provider thành adapter gọi service thay vì giữ business logic trong `src.cli`.
- Đổi import prompt-refinement kappa sang public surface `src.services.post_validation`.
- Đưa CSV/parquet tabular I/O chung vào `backend/src/utils/tabular_io.py`; service phase không còn sở hữu helper đọc bảng.
- Rename helper đọc output dự đoán của model sang `model_predictions.py` để tránh lẫn với truth labels.
- Bỏ config OpenAI không còn được backend dùng khỏi `app_config.py` và `.env.example`; giữ phase defaults cạnh service, không đưa vào app config/YAML.
- Đổi hằng phase sang tên không có tiền tố `DEFAULT_` và dọn reference cũ `src.utils.validation_aggregation` / `src.utils.dataset_split`.

**Files thay đổi:**
- `backend/src/services/post_validation/` — created
- `backend/src/cli.py`, `backend/src/providers/validation_provider.py` — modified
- `backend/src/app_config.py`, `backend/.env.example` — modified
- `backend/src/utils/tabular_io.py` — created
- `backend/src/services/prompt_refinement/evaluator.py` — modified
- `backend/src/utils/dataset_split.py`, `backend/src/utils/validation_aggregation/*` — deleted
- `backend/tests/test_dataset_split.py`, `backend/tests/test_validation_aggregation.py` — modified
- `docs/en/template/post-validation.md`, `docs/vi/template/post-validation.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Post-validation giờ có service boundary theo phase: `ValidationAggregationService` tạo vote/validated/review outputs, `ArtifactDetectionService` chạy PMI artifact detection, `ParaphraseService` apply/promote paraphrase, và `DatasetSplitService` ghi train/dev/test split. CLI command và MCP provider vẫn giữ public command/tool name hiện tại để tương thích, nhưng không còn sở hữu business logic. Config runtime/env chỉ còn MLflow trong `app_config`; các default như PMI threshold, split ratio, seed, group/label column sống cạnh service vì là behavior mặc định của phase.

---

### [2026-06-27 23:23] — [Validation] Remove duplicate verification schema

**Đã làm:**
- Xoá schema verification riêng của validation vì runtime đang dùng shared response từ progress tracker.
- Gỡ export schema trùng khỏi `backend/src/schemas/__init__.py`.
- Rà validation runtime/provider sau gen cleanup: các provider methods còn lại là MCP public boundary; private service helpers còn lại đều có logic domain hoặc CSV/runtime responsibility.

**Files thay đổi:**
- `backend/src/schemas/validation_runtime_schema.py` — modified
- `backend/src/schemas/__init__.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Validation progress verification dùng chung `ProgressTrackingService.verify_progress_log(...)`, nên response shape không cần schema validation-specific riêng. Blind validation vẫn giữ flow: start validation run, claim masked rows, submit verdicts, compare against hidden label with `to_label_name(...)`, write batch CSVs, finalize into `validation_results.csv`, then cleanup state.

---

### [2026-06-27 23:06] — [Generation] Remove thin private helpers

**Đã làm:**
- Inline generation finalize merge call trực tiếp sang shared `_merge_batch_csv(...)`.
- Inline label comparison trong batch-result validation thay vì giữ helper một dòng.
- Sửa mô tả MCP `start_generation_run` để nói đúng public contract `from_sample`/`to_sample` là one-based sample range.
- Đồng bộ ví dụ output path trong provider/execution skill về `data/generated/...`
  để khớp convention runtime hiện tại.

**Files thay đổi:**
- `backend/src/services/generation_run_service.py` — modified
- `backend/src/providers/generation_provider.py` — modified
- `backend/skills/execution.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Generation service vẫn giữ nguyên lifecycle: start, claim, validate submit, write batch, finalize/cleanup. Cleanup này chỉ bỏ hai wrapper private không còn mang domain meaning sau khi merge logic chung vào `BaseRunService`; provider vẫn là MCP boundary public nên không inline xuống service.

---

### [2026-06-27 23:00] — [Generation] Remove stale scheduling guidance

**Đã làm:**
- Xoá tool lập kế hoạch batch cũ khỏi generation tool map và generation phase trong MCP instructor skill.
- Bỏ công thức pool worker khỏi delegation skill; subagent scheduling giờ là trách nhiệm của connected harness khi user/template yêu cầu.
- Cập nhật generator templates EN/VI để không hướng dẫn suy ra số worker từ backend.
- Xoá mô tả integrity-log cũ khỏi progress-tracking skill và thay bằng mô tả JSONL verification thực tế.

**Files thay đổi:**
- `backend/skills/instructor.md` — modified
- `backend/skills/progress_tracking.md` — modified
- `backend/skills/delegation.md` — modified
- `docs/en/template/generator.md`, `docs/vi/template/generator.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Generation MCP flow hiện chỉ còn runtime tools thật: `start_generation_run`, `claim_next_batch`, `submit_batch_result`, progress/claim release, verify, finalize, list. Backend không còn được mô tả như nơi tính kế hoạch worker; nếu prompt/user muốn dùng subagents thì connected harness tự schedule sau khi đã claim batch qua MCP. Progress log vẫn là append-only JSONL; verification hiện kiểm consistency/reconciliation theo event content.

---

### [2026-06-27 20:25] — [PromptRefinement] Remove backend proposal tool

**Đã làm:**
- Baseline trước khi sửa: prompt-refinement targeted suite pass với `29 passed`.
- Xoá `PromptRefinementStrategy` và service path `propose_update(...)` vì backend không nên tự viết prompt-update proposal thay agent.
- Gỡ MCP tool `propose_prompt_refinement_update`; `evaluate_prompt_refinement` vẫn là contract duy nhất cho calibration, kappa, decision, MLflow logging.
- Cập nhật README, skill, instructor, flow docs, templates, tests, và CLI wording để failed round trở thành agent-owned evidence review dựa trên `disagreement_rows.csv`.
- Verify sau sửa: prompt-refinement targeted suite `28 passed`; CLI suite `34 passed`; full backend suite `158 passed`.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/refinement_strategy.py` — deleted
- `backend/src/services/prompt_refinement/service.py`, `backend/src/services/prompt_refinement/models.py` — modified
- `backend/src/schemas/prompt_refinement_schema.py`, `backend/src/providers/validation_provider.py`, `backend/src/cli.py` — modified
- `backend/skills/instructor.md`, `backend/skills/prompt_refinement.md` — modified
- `README.md`, `README.vi.md`, `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `backend/tests/test_prompt_refinement_service.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement backend giờ chỉ evaluate/log một calibration và trả `accepted` hoặc `needs_prompt_update`. Khi kappa thấp, main agent đọc evidence đã log như `disagreement_rows.csv`, prompt snapshots, verdict files, và calibration rows rồi report next step nhỏ nhất cho user duyệt; backend không propose prompt edit, không spawn editor agents, không lock/version/promote prompts, và không tự chạy round tiếp theo.

---

### [2026-06-27 19:55] — [Runtime] Implement run-service gen/val cleanup

**Đã làm:**
- Tạo branch `refactor/run-service-gen-val-cleanup` để implement plan refactor runtime.
- Baseline targeted suite trước khi sửa: generation/validation service + provider tests đều pass.
- Inline `GenerationRunService._merge_batch_outputs(...)` vào finalize path và xoá wrapper một dòng.
- Bỏ `GenerationRunService._label_key(...)`, giữ label preservation bằng so sánh `str(...)` trực tiếp.
- Inline acceptance counting và CSV bool parse trong `ValidationRunService`, xoá `_count_acceptance(...)` và `_csv_bool(...)`.
- Giữ nguyên public MCP tool surface, provider split hiện tại, output schema, progress lifecycle, và validation label-normalization boundary.
- Đồng bộ wording `verify_progress_log` sang consistency/reconciliation checks, tránh gợi lại contract progress log cũ đã bị loại bỏ.

**Files thay đổi:**
- `backend/src/services/base_run_service.py` — modified
- `backend/src/services/generation_run_service.py` — modified
- `backend/src/services/validation_run_service.py` — modified
- `backend/src/providers/generation_provider.py`, `backend/src/providers/validation_provider.py` — modified
- `docs/en/project-overview.md`, `docs/vi/project-overview.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Refactor này chỉ xoá helper private không còn mang domain meaning. Generation vẫn giữ exact label preservation theo source label; validation vẫn dùng `to_label_name(...)` trong `_labels_match(...)` để kiểm 3-class strict. Progress verification hiện là consistency/reconciliation scan trên append-only JSONL events, không phải chained-log verification. Provider methods vẫn là public MCP adapters nên không bị xoá dù đa phần forward xuống service.

---

### [2026-06-27 17:41] — [Runtime] Plan run-service gen/val cleanup

**Đã làm:**
- Rà lại `BaseRunService`, `GenerationRunService`, `ValidationRunService`, hai provider hiện còn lại, provider tests, và flow/template docs liên quan.
- Tạo plan refactor tập trung vào helper private dư sau khi đã loại bớt provider/tool prompt-refinement trước đó.
- Phân loại method nên inline/delete, method nên giữ vì là boundary public MCP hoặc lifecycle invariant.
- Chốt hướng không re-split provider trong slice này để tránh thêm layer ngay sau khi vừa giảm provider surface.

**Files thay đổi:**
- `docs/superpowers/plans/refactor-run-service-gen-val-cleanup.md` — created
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Chưa implement; đây là plan-only artifact cho vòng refactor tiếp theo.

**Flow explained:**
Plan này giữ public MCP tool surface ổn định: gen/val provider methods là transport adapters, không bị xem là dead code chỉ vì pass-through. Cleanup đề xuất trước tiên chỉ đụng private helper như `_merge_batch_outputs(...)` và `_label_key(...)`; validation helper một-dòng được xử lý tùy readability. Nếu sau này muốn tách prompt-refinement/post-validation khỏi `ValidationToolProvider`, đó là một follow-up riêng vì hiện docs/tests vẫn xem các tool đó là contract đang dùng.

---

### [2026-06-27 17:27] — [PromptRefinement] Run low-effort 3-subagent smoke calibration

**Đã làm:**
- Freeze 10 source_uid đầu tiên từ `backend/data/generated/anli_1_16946.csv` thành một calibration slice nhỏ cho smoke run.
- Dispatch 3 validator subagent độc lập với ba model `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini` ở `low` effort, giữ blind labels và thu đúng một verdict file cho mỗi model.
- Retry hai model một lần vì `reason` chưa sạch tiếng Việt hoàn toàn, rồi rewrite verdict CSV bằng writer chuẩn sau khi MCP parser báo lỗi quoting.
- Chạy `evaluate_prompt_refinement` với `generator_skill_name=generator_plain`; kết quả `kappa=0.8744769874476985`, `decision=accepted`, `rejected_sample_count=1`, `bundle_id=calibration`, `mlflow_run_id=7262e580eea040a393662cfe51db5250`.
- Xác nhận artifact `disagreement_rows.csv` của run chỉ còn 1 UID bất đồng là `source_uid=2`.

**Files thay đổi:**
- `data/prompt-refinement/2026-06-27-low-effort-smoke/calibration/calibration.csv` — created
- `data/prompt-refinement/2026-06-27-low-effort-smoke/calibration/masked_rows.csv` — created
- `data/prompt-refinement/2026-06-27-low-effort-smoke/calibration/verdicts/gpt-5.5.csv` — created
- `data/prompt-refinement/2026-06-27-low-effort-smoke/calibration/verdicts/gpt-5.4.csv` — created
- `data/prompt-refinement/2026-06-27-low-effort-smoke/calibration/verdicts/gpt-5.4-mini.csv` — created
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Smoke run này dùng đúng template connected-agent hiện tại: main agent giữ calibration source có label, chỉ phát masked rows cho validators, kiểm schema rồi mới persist verdicts và gọi MCP evaluation. Vì `kappa` vượt ngưỡng 0.85 nên flow dừng ở `accepted`; không gọi `propose_prompt_refinement_update`, không sửa prompt, không lock/version/promote gì thêm.

---

### [2026-06-27 17:15] — [PromptRefinement] Align docs with connected-agent flow

**Đã làm:**
- Bỏ hướng dẫn MLflow URL/port/startup khỏi README prompt-refinement section và prompt-refinement templates.
- Cập nhật template EN/VI để agent chỉ tập trung load skills, tạo calibration dataset, dispatch ba validator độc lập, ghi verdicts, rồi gọi `evaluate_prompt_refinement` và `propose_prompt_refinement_update` khi cần.
- Cập nhật skill/validator flow docs để nói rõ connected `nli-tools` runtime sở hữu tool execution và calibration logging.
- Thêm regression guard để prompt-refinement templates không quay lại `tracking_uri`, `experiment_name`, local URL, hoặc server-start commands.

**Files thay đổi:**
- `README.md`, `README.vi.md` — modified
- `backend/skills/instructor.md`, `backend/skills/prompt_refinement.md` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `backend/tests/test_skill_service.py` — modified

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement template giờ giả định agent đã connect sẵn với `nli-tools` và thấy skill/tool surface. Template không còn yêu cầu agent truyền MLflow tracking config hoặc đọc hướng dẫn service startup; phần cần làm chỉ còn chuẩn bị fixed calibration rows, giữ validators blind, persist đúng ba verdict files, chạy `evaluate_prompt_refinement`, và gọi `propose_prompt_refinement_update` khi `needs_prompt_update`.

---

### [2026-06-27 13:06] — [PromptRefinement] Switch to single-run proposal tool

**Đã làm:**
- Đổi proposal boundary từ auto artifact trong `evaluate_prompt_refinement` sang MCP tool riêng `propose_prompt_refinement_update` để harness chủ động lấy proposal cho user sau khi calibration kết thúc.
- Rename strategy nội bộ thành `PromptRefinementStrategy.propose(...)`; bỏ naming `PromptAugmentStrategy` khỏi service code.
- `evaluate_prompt_refinement` giờ chỉ evaluate/log một calibration và trả kappa/decision/MLflow run; không còn `round_number` hoặc `change_summary`.
- Đổi field đếm disagreement sang `rejected_sample_count` trong response schema, MLflow metric, tests, và docs để nói rõ đây là số sample không chấp nhận.
- Giữ behavior single-run: backend không register prompt versions, không promote aliases, không lock prompts, không spawn editor agents, và không tự rerun.
- Cập nhật README, skill, provider schema, validator flow docs, templates, và tests theo handoff proposal-tool.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/refinement_strategy.py` — created/renamed from augment strategy
- `backend/src/services/prompt_refinement/augment_strategy.py` — deleted
- `backend/src/services/prompt_refinement/models.py` — modified
- `backend/src/services/prompt_refinement/service.py` — modified
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `backend/src/services/prompt_refinement/evaluator.py` — modified
- `backend/src/schemas/prompt_refinement_schema.py` — modified
- `backend/src/providers/validation_provider.py` — modified
- `backend/src/cli.py` — modified
- `backend/skills/prompt_refinement.md` — modified
- `backend/skills/instructor.md` — modified
- `README.md`, `README.vi.md` — modified
- `backend/tests/test_prompt_refinement_service.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_skill_service.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `docs/en/template/prompt-refinement-editor-*.md`, `docs/vi/template/prompt-refinement-editor-*.md` — deleted

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement backend giờ dừng ở một lần calibration kappa. `evaluate_prompt_refinement` log metrics/verdicts/prompt snapshots/`disagreement_rows.csv` vào MLflow và trả `needs_prompt_update` hoặc `accepted`; nó không tự tạo proposal artifact. Nếu `kappa < 0.85`, harness gọi `propose_prompt_refinement_update` với cùng `verdicts_dir`, `calibration_input`, và `generator_skill_name` để nhận `reason`, `suggested_action`, và `evidence_uids` rồi report cho user. User vẫn tự sửa skill thủ công nếu muốn; backend không lock, không version/promote prompt, không spawn editor agents, và không tự chạy calibration tiếp theo.
