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

---

### [2026-06-26 22:15] — [PromptRefinement] Extract prompt lock service

**Đã làm:**
- Tách `confirm_prompt_lock` khỏi `mlflow_store.py` sang module riêng `locking.py`.
- Tạo `mlflow_support.py` để share MLflow client setup và prompt-name constants giữa round logging với lock flow.
- Đổi `PromptRefinementService` sang compose `PromptRefinementLockService` thay vì để `PromptRefinementMlflowStore` ôm cả logging lẫn locking.
- Giữ nguyên MCP/provider/service API và verify lại regression suite của prompt refinement.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/locking.py` — created
- `backend/src/services/prompt_refinement/mlflow_support.py` — created
- `backend/src/services/prompt_refinement/mlflow_store.py` — modified
- `backend/src/services/prompt_refinement/service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** `mlflow_store.py` vẫn còn là module round-logging khá dày; vòng sau có thể tách tiếp registration/logging steps nếu cần. Nếu tiếp tục tối giản contract, có thể bỏ hẳn URL presentation concern khỏi prompt-refinement response.

**Flow explained:**
Prompt-refinement giờ tách lock path ra rõ hơn: `PromptRefinementService.confirm_prompt_lock()` chỉ delegate sang `PromptRefinementLockService`, module này chịu trách nhiệm load eligible run, validate exact evaluated prompt URIs/versions, set `locked` aliases, và mark session/run state. `PromptRefinementMlflowStore` chỉ còn ownership cho evaluate-round logging/register/candidate alias, nên boundary giữa `round logging` và `lock confirmation` rõ hơn mà không đổi public contract.

---

### [2026-06-26 20:01] — [DispatchPlanning] Remove worker-count guidance from generator templates

**Đã làm:**
- Bỏ công thức `assigned_samples`, `total_batches`, và worker cap khỏi generator flow/template EN/VI.
- Đổi wording còn sót từ `parallel worker` sang `subagent` để không ám chỉ backend có worker model.
- Giữ nguyên runtime claim/submit/finalize; chỉ bỏ guidance tính toán worker ở lớp docs/prompt.

**Files thay đổi:**
- `README.md` — modified
- `backend/src/providers/generation_provider.py` — modified
- `docs/en/flow/generator.md`, `docs/vi/flow/generator.md` — modified
- `docs/en/template/generator.md`, `docs/vi/template/generator.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Generator runtime không có khái niệm worker count nữa ở cả code lẫn template. Agent có thể chạy tuần tự hoặc tự spawn bao nhiêu subagent tùy context, nhưng backend chỉ biết các mutation có state thật: `start_generation_run`, `claim_next_batch`, `submit_batch_result`, `verify_progress_log`, `finalize_generation_run`.

---

### [2026-06-26 19:44] — [DispatchPlanning] Remove redundant dispatch planning tool

**Đã làm:**
- Xoá service/router/provider/schema/test riêng cho `calculate_dispatch_plan` vì tool chỉ bọc phép tính agent có thể tự làm.
- Gỡ registration MCP tool và REST route `/api/dispatch-plan/calculate` khỏi app wiring.
- Chuyển default batch size `20` sang shared run lifecycle constant để generation/validation không phụ thuộc dispatch module.
- Cập nhật generator flow/templates EN/VI và project overview để agent tự tính batch/worker khi dùng subagents.

**Files thay đổi:**
- `backend/src/main.py` — modified
- `backend/src/providers/__init__.py`, `backend/src/services/__init__.py`, `backend/src/schemas/__init__.py` — modified
- `backend/src/services/base_run_service.py`, `backend/src/services/generation_run_service.py`, `backend/src/services/validation_run_service.py` — modified
- `backend/src/providers/generation_provider.py`, `backend/src/providers/validation_provider.py` — modified
- `backend/src/services/dispatch_planning_service.py` — deleted
- `backend/src/routers/dispatch_plan_router.py` — deleted
- `backend/src/providers/dispatch_planning_provider.py` — deleted
- `backend/src/schemas/dispatch_plan_schema.py` — deleted
- `backend/tests/test_dispatch_planning_service.py`, `backend/tests/test_dispatch_plan_router.py` — deleted
- `backend/tests/test_generation_provider.py` — modified
- `docs/en/flow/generator.md`, `docs/vi/flow/generator.md` — modified
- `docs/en/template/generator.md`, `docs/vi/template/generator.md` — modified
- `docs/en/project-overview.md`, `docs/vi/project-overview.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Dispatch planning không còn là backend-owned runtime contract. Agent vẫn dùng `start_generation_run` để tạo run và `claim_next_batch` để lấy batch thật; nếu muốn chạy subagents song song thì agent tự tính `assigned_samples = to_sample - from_sample + 1`, `total_batches = ceil(assigned_samples / batch_size)`, rồi giữ số worker trong cap operator cho phép. Backend chỉ giữ các tool có side effect/runtime state: start, claim, submit, verify, finalize.

---

### [2026-06-26 10:39] — [PromptRefinement] Split prompt-refinement service modules

**Đã làm:**
- Tách `PromptRefinementService` monolith thành package `backend/src/services/prompt_refinement/` theo trách nhiệm: evaluator, MLflow store, evidence pack, locking, facade.
- Xoá shim `backend/src/services/prompt_refinement_service.py` vì dependency nội bộ đã chuyển sang package import.
- Đổi MCP provider và service tests sang import `PromptRefinementService` từ `src.services.prompt_refinement`.
- Đổi default MLflow tracking URI, experiment name, và artifact root từ hardcode trong service/provider sang `app_config.MLFLOW_*`.
- Xoá backend editor-task prompt generator; harness dùng static editor templates với evidence directory.
- Tách contract/schema của prompt-refinement sang `prompt_refinement_schema.py`, gồm evaluation, MLflow registration và response DTOs.
- Bỏ calibration dataset/UID-set hash khỏi refinement contract, response, MLflow params/tags/artifacts và evidence summary.
- Không thêm backend auto-refinement loop, không spawn subagents, không đụng generation/validation runtime/PMI/split.

**Files thay đổi:**
- `backend/src/services/prompt_refinement/__init__.py` — created
- `backend/src/services/prompt_refinement/evaluator.py` — created
- `backend/src/services/prompt_refinement/mlflow_store.py` — created
- `backend/src/services/prompt_refinement/evidence_pack.py` — created
- `backend/src/services/prompt_refinement/editor_tasks.py` — deleted
- `backend/src/services/prompt_refinement/service.py` — created
- `backend/src/services/prompt_refinement_service.py` — deleted
- `backend/src/app_config.py` — modified
- `backend/src/providers/validation_provider.py` — modified
- `backend/src/schemas/prompt_refinement_schema.py` — created
- `backend/src/schemas/validation_runtime_schema.py` — modified
- `backend/tests/test_prompt_refinement_service.py` — modified
- `backend/tests/test_validation_provider.py` — modified
- `backend/tests/test_skill_service.py` — modified
- `backend/skills/instructor.md`, `backend/skills/prompt_refinement.md` — modified
- `README.md`, `README.vi.md`, `docs/en/*`, `docs/vi/*` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt-refinement backend giờ là facade mỏng: `evaluator.py` giữ verdict discovery, calibration checks, kappa/disagreement evidence; `mlflow_store.py` giữ prompt registry/run/session/candidate-alias/locked-alias side effects; `evidence_pack.py` chỉ ghi failed-round evidence files. `prompt_refinement_schema.py` là nơi sở hữu các data contract của refinement: `PromptRoundEvaluation`, `PromptBundleRegistration`, và các response DTOs; `validation_runtime_schema.py` chỉ còn validation-run schema. Refinement không còn ghi hash field; session grouping chỉ chặn reuse sau khi finalized/locked, còn việc giữ cùng calibration UID set giữa comparable rounds là operator convention. Public import nội bộ là `src.services.prompt_refinement.PromptRefinementService`; không còn wrapper file cùng cấp trong `services/`. Default MLflow URL, experiment name, và artifact root nằm ở `app_config.MLFLOW_*` nhưng các tool/service vẫn nhận override. Backend chỉ chuẩn bị evaluation/evidence/lock; editor subagent prompts thuộc harness/static templates, không còn API tool tạo task payload.

---

### [2026-06-25 20:35] — [ProgressTracking] Remove progress hash-chain verification

**Đã làm:**
- Bỏ hash-chain `prev_hash` khỏi `progress.jsonl` events vì progress log chỉ cần phục vụ resume/audit runtime, không cần giả lập ledger tamper-proof.
- Bỏ `broken_hashes` khỏi response schema generation/validation progress verification.
- Giữ `verify_progress_log` và `verify_validation_progress_log`, nhưng chỉ kiểm các invariant thực dụng: duplicate done rows, done/skip overlap, missing batch files, count mismatches, active claims.
- Đổi tests hash tamper sang duplicate-row và missing-batch-file failure modes.

**Files thay đổi:**
- `backend/src/services/progress_tracking_service.py` — modified
- `backend/src/schemas/generation_runtime_schema.py` — modified
- `backend/src/schemas/validation_runtime_schema.py` — modified
- `backend/tests/test_generation_run_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Progress tracking vẫn append JSONL event theo `agent-{sequence}` và vẫn replay state như trước. Verification không còn check cryptographic chain; nó chỉ xác nhận trạng thái pipeline có nhất quán đủ để finalize an toàn.

---

### [2026-06-25 13:05] — [ValidationIntegrity] Upgrade final split to grouped stratification

**Đã làm:**
- Nâng split stage cuối từ grouped shuffle theo row target sang grouped-stratified greedy vẫn giữ premise/group anti-leakage.
- Giữ row ratio là constraint chi phối; label/domain distribution chỉ dùng để cân bằng trong các candidate hợp lý về size.
- Thêm optional `--domain-column` để cân bằng thêm domain/subdomain khi có dữ liệu usable; thiếu/rỗng thì manifest ghi status và split vẫn chạy.
- Mở rộng manifest để audit strategy, seed, ratios, global/split label distribution, và domain status/distribution.
- Thêm regression test chặn lỗi collapse row ratio kiểu `train=1, dev=41, test=38` trên 80 rows / 33 groups.
- Cập nhật flow/template docs EN/VI cho final split mới.

**Files thay đổi:**
- `backend/src/utils/dataset_split.py` — modified
- `backend/src/cli.py` — modified
- `backend/tests/test_dataset_split.py`, `backend/tests/test_cli.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/en/template/post-validation.md`, `docs/vi/template/post-validation.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Split cuối vẫn assign theo `group_column` nên mọi row cùng premise không thể đi sang nhiều split. Strategy mặc định `grouped-stratified` shuffle group theo seed, ưu tiên group lớn/hiếm, rồi chọn split theo row-progress alignment với target ratios trước khi xét label/domain tie-break. Runtime check trên `data/validated/anli1-100/post/promoted_dataset.csv` ra `train=64, dev=8, test=8` và `premise_cross_split_leaks=0`.

---

### [2026-06-25 12:25] — [OutputConvention] Align agent templates to data directories

**Đã làm:**
- Xoá repo-root artifact directory `outputs/` vừa phát sinh.
- Đổi generator template output sang `data/generated/<RUN_OR_DATASET_ID>.csv`.
- Đổi validator template output sang `data/validated/<RUN_OR_MODEL_ID>`.
- Đổi post-validation template output sang `data/validated/<RUN_OR_DATASET_ID>` và `data/splits/<RUN_OR_DATASET_ID>`.
- Đổi prompt-refinement template output root sang `data/prompt-refinement/<SESSION_ID_OR_DATASET_ID>`.
- Thêm test guardrail để agent templates không trôi lại về repo-root `outputs/`.

**Files thay đổi:**
- `docs/en/template/generator.md`, `docs/vi/template/generator.md` — modified
- `docs/en/template/validator.md`, `docs/vi/template/validator.md` — modified
- `docs/en/template/post-validation.md`, `docs/vi/template/post-validation.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Existing deleted tracked data file `backend/data/validation/validation_masked.csv` vẫn đang là worktree state riêng, không thuộc cleanup này.

**Flow explained:**
Agent-facing templates giờ dùng `data/...` làm output convention thống nhất. Runtime artifacts không nên ghi vào repo-root `outputs/`; generation, validation, post-validation, split, và prompt-refinement đều có placeholder dưới `data/` để khớp cấu trúc backend/data khi operator nhìn project tree.

---
