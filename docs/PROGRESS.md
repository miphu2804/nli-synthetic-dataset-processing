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

---

### [2026-06-27 02:35] — [PromptRefinement] Remove backend evidence-pack helper

**Đã làm:**
- Xoá MCP tool `prepare_prompt_refinement_evidence_pack` khỏi validation provider.
- Xoá `PromptRefinementService.prepare_evidence_pack(...)`, response schema tương ứng, và writer module `review_artifacts.py`.
- Cập nhật prompt-refinement skill/template/docs để failed-round refine do harness tự inspect MLflow artifacts và tự loop round tiếp theo.
- Cập nhật tests để assert evidence-pack helper không còn là backend-owned tool.

**Files thay đổi:**
- `backend/src/providers/validation_provider.py` — modified
- `backend/src/services/prompt_refinement/service.py` — modified
- `backend/src/schemas/prompt_refinement_schema.py` — modified
- `backend/src/services/prompt_refinement/review_artifacts.py` — deleted
- `backend/tests/test_prompt_refinement_service.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_skill_service.py` — modified
- `backend/skills/instructor.md`, `backend/skills/prompt_refinement.md` — modified
- `README.md`, `README.vi.md` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement backend giờ chỉ đo một round, ghi MLflow artifacts, trả decision và hỗ trợ explicit lock. Khi `decision=refine_prompt`, harness đọc artifacts của MLflow run như `disagreement_rows.csv`, `prompt_bundle.json`, calibration manifest và verdict files để quyết định sửa prompt hoặc chạy round tiếp theo; backend không còn tạo local evidence pack, không spawn editor agents, và không giữ method thủ công cho refine loop.

---

### [2026-06-27 02:15] — [PromptRefinement] Remove thin MLflow support module

**Đã làm:**
- Xoá `backend/src/services/prompt_refinement/mlflow_support.py` vì module này chỉ giữ hai prompt-name constants và một helper setup client quá mỏng.
- Chuyển ownership đoạn tạo `MlflowClient` về sát nơi dùng thật là `mlflow_store.py` và `locking.py`.
- Giữ nguyên prompt registry names `nli-generator` và `nli-validator`, không đổi flow evaluate/evidence-pack/lock.
- Verify lại full prompt-refinement targeted suite sau cleanup.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `backend/src/services/prompt_refinement/locking.py` — modified
- `backend/src/services/prompt_refinement/mlflow_support.py` — deleted
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
MLflow client setup giờ không còn bị tách thành một “support” module chung chỉ để né vài dòng duplicate. `PromptRefinementMlflowStore` và `PromptRefinementLockService` mỗi nơi tự sở hữu helper tạo client của mình; như vậy dependency graph thẳng hơn và đọc module là thấy ngay phần MLflow setup phục vụ flow nào.

---

### [2026-06-27 02:00] — [PromptRefinement] Refactor evaluator and MLflow round logging internals

**Đã làm:**
- Inline response construction trong `locking.py` và xoá `_build_response(...)` vì helper không có reuse thực.
- Đổi naming trong `evaluator.py` sang explicit round-evaluation language: entrypoint `evaluate_round_inputs(...)` và các helper private theo trách nhiệm đọc/validate/build.
- Tách `mlflow_store.py::log_evaluated_round(...)` theo stage helper rõ hơn: build tags, create round run, register prompts, log metadata/artifacts, set candidate aliases, và best-effort session metrics.
- Thêm regression test xác nhận nếu MLflow nổ khi register prompt thì round run bị mark `FAILED`.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/locking.py` — modified
- `backend/src/services/prompt_refinement/evaluator.py` — modified
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `backend/src/services/prompt_refinement/service.py` — modified
- `backend/tests/test_prompt_refinement_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement vẫn giữ nguyên public contract và semantics cũ, nhưng internal flow giờ đọc theo stage tự nhiên hơn. `service.py` vẫn là facade mỏng; `evaluator.py` nói rõ nó đang evaluate một refinement round chứ không phải “inputs” chung chung; `mlflow_store.py` vẫn là một MLflow store duy nhất nhưng orchestration của round logging đã được tách theo bước để review/fix an toàn hơn, trong khi branch get/create experiment và session vẫn visible ngay trong method chính.

---

### [2026-06-27 01:20] — [PromptRefinement] Add follow-up refactor continuation plan

**Đã làm:**
- Tạo continuation plan mới cho prompt-refinement follow-up refactor sau các bước đã merge trước đó.
- Chốt scope tiếp theo là: inline helper thừa trong `locking.py`, làm explicit naming trong `evaluator.py`, và tách stage trong `mlflow_store.py::log_evaluated_round(...)`.
- Ghi rõ non-goals để tránh drift sang behavior change: không đổi MCP/service contract, không đổi session semantics, không đụng cleanup các file tạm local.
- Bổ sung khuyến nghị thêm một regression test cho round-failure path của MLflow logging vì đây là vùng rủi ro cao nhất khi tách nhỏ orchestration.

**Files thay đổi:**
- `docs/superpowers/plans/refactor-prompt-refinement-followups.md` — created
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Chưa implement; đây là plan-only artifact cho vòng refactor kế tiếp.

**Flow explained:**
Prompt-refinement đã qua phase tách module lớn. Vòng tiếp theo không đổi ownership nữa mà làm gọn readability trong từng module còn lại: `locking.py` bỏ helper vô nghĩa, `evaluator.py` đổi sang naming theo use case round evaluation, còn `mlflow_store.py` vẫn giữ một store duy nhất nhưng tách orchestration của round logging theo stage rõ ràng để dễ review và khó sai failure boundary hơn.

---
