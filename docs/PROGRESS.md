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

### [2026-06-27 00:45] — [RepoGuidance] Add commit message convention to CLAUDE.md

**Đã làm:**
- Thêm rule commit message theo format `type(scope): content` vào `CLAUDE.md`.
- Ghi rõ các type nên dùng: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
- Thêm ví dụ scope gần domain hiện tại như `prompt-refinement`, `validation`, `dispatch`.
- Cấm style commit tự do kiểu không có `type(scope):`.

**Files thay đổi:**
- `CLAUDE.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Repo hiện chưa có hook tự enforce commit-message lint; rule mới đang là guideline trong repo docs.

**Flow explained:**
Từ đây commit trong repo này nên theo conventional style thống nhất để dễ đọc lịch sử thay đổi theo business area. `scope` phải bám domain thực tế thay vì mô tả mơ hồ, và content giữ ngắn, imperative.

---

### [2026-06-27 00:20] — [PromptRefinement] Rename evidence-pack internals to review artifacts

**Đã làm:**
- Đổi internal module `evidence_pack.py` thành `review_artifacts.py` để naming gần domain review hơn.
- Đổi class `PromptRefinementEvidencePackWriter` thành `PromptRefinementReviewArtifactsWriter`.
- Đổi internal writer method `write_evidence_pack(...)` thành `write_review_artifacts(...)`.
- Giữ nguyên public service/MCP contract `prepare_prompt_refinement_evidence_pack` để không vỡ caller hiện có.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/review_artifacts.py` — created (moved from `evidence_pack.py`)
- `backend/src/services/prompt_refinement/service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Public API và docs vẫn dùng từ `evidence pack`; nếu muốn thống nhất naming hoàn toàn thì sẽ là một vòng contract change riêng.

**Flow explained:**
Prompt-refinement vẫn expose cùng workflow/tool như cũ, nhưng naming nội bộ giờ phản ánh đúng hơn việc module này chỉ ghi các artifact phục vụ failed-round review. Nhờ đó service facade đọc tự nhiên hơn: evaluate -> log round -> write review artifacts -> confirm lock.

---

### [2026-06-27 00:05] — [PromptRefinement] Split MLflow get/create helpers

**Đã làm:**
- Bỏ pattern `resolve_*` trong `prompt_refinement/mlflow_store.py` để tránh helper vừa đọc vừa có thể tạo side effect.
- Tách flow experiment thành `_get_experiment_by_name(...)` và `_create_experiment(...)`.
- Tách flow session run thành `_get_active_session_run(...)` và `_create_session_run(...)`.
- Giữ orchestration get-or-create ở `log_evaluated_round(...)` để branch logic nhìn thấy ngay tại use case chính.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Naming trong các module khác như `evidence_pack` và một số `extract/build` helpers vẫn có thể tinh chỉnh tiếp, nhưng chưa đổi trong vòng này để giữ scope hẹp.

**Flow explained:**
Prompt-refinement MLflow round logging giờ explicit hơn: code trước hết thử lấy experiment/session run hiện có, nếu chưa có mới gọi create path tương ứng. Helper không còn giấu side effect dưới tên `resolve`, nên nhìn vào `log_evaluated_round(...)` là thấy ngay chỗ nào chỉ đọc và chỗ nào có thể mutate MLflow state.

---

### [2026-06-26 22:35] — [PromptRefinement] Drop MLflow run URL from responses

**Đã làm:**
- Bỏ `mlflow_run_url` khỏi prompt-refinement response schema cho cả evaluate-round và lock-confirmation path.
- Xoá `build_run_url` khỏi shared MLflow support vì feature không còn trả UI link.
- Giữ lại MLflow identifiers thật sự cần cho flow: `mlflow_run_id`, `mlflow_session_run_id`, `bundle_id`, prompt versions.
- Đồng bộ template/skill text để report chỉ còn MLflow run ID thay vì run URL.

**Files thay đổi:**
- `backend/src/schemas/prompt_refinement_schema.py` — modified
- `backend/src/services/prompt_refinement/mlflow_support.py` — modified
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `backend/src/services/prompt_refinement/locking.py` — modified
- `backend/src/services/prompt_refinement/service.py` — modified
- `backend/skills/prompt_refinement.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Prompt-refinement vẫn còn vài tên thiên về orchestration như `evidence_pack`; chưa đổi trong vòng này để giữ scope hẹp.

**Flow explained:**
Prompt-refinement giờ chỉ expose MLflow identifiers để operator hoặc automation tự truy cập qua API/UI khi cần. Feature code không còn ghép browser URL presentation string, nên lock/evaluate responses gọn hơn và ít dính UI concern hơn.
