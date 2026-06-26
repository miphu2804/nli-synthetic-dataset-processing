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
- `backend/src/services/prompt_refinement/locking.py` — created
- `backend/src/services/prompt_refinement/service.py` — created
- `backend/src/services/prompt_refinement_service.py` — deleted
- `backend/src/app_config.py` — modified
- `backend/src/providers/validation_provider.py` — modified
- `backend/src/services/prompt_refinement/locking.py` — modified
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
Prompt-refinement backend giờ là facade mỏng: `evaluator.py` giữ verdict discovery, calibration checks, kappa/disagreement evidence; `mlflow_store.py` giữ prompt registry/run/session/candidate-alias side effects; `evidence_pack.py` chỉ ghi failed-round evidence files; `locking.py` chỉ lock exact prompt versions từ eligible MLflow run. `prompt_refinement_schema.py` là nơi sở hữu các data contract của refinement: `PromptRoundEvaluation`, `PromptBundleRegistration`, và các response DTOs; `validation_runtime_schema.py` chỉ còn validation-run schema. Refinement không còn ghi hash field; session grouping chỉ chặn reuse sau khi finalized/locked, còn việc giữ cùng calibration UID set giữa comparable rounds là operator convention. Public import nội bộ là `src.services.prompt_refinement.PromptRefinementService`; không còn wrapper file cùng cấp trong `services/`. Default MLflow URL, experiment name, và artifact root nằm ở `app_config.MLFLOW_*` nhưng các tool/service vẫn nhận override. Backend chỉ chuẩn bị evaluation/evidence/lock; editor subagent prompts thuộc harness/static templates, không còn API tool tạo task payload.

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

### [2026-06-25 12:10] — [PostValidation] Add post-validation orchestration template

**Đã làm:**
- Thêm post-validation template EN/VI cho consensus + PMI, optional paraphrase, revalidation promotion, và final split.
- Template dùng MCP `run_consensus_pmi` và `promote_paraphrase_revalidation`.
- Template giữ `apply-paraphrase` và `split` là deterministic CLI stages.
- Ghi rõ revalidation queue có `label=""` nên không gọi `start_validation_run`; orchestrator dispatch đúng ba validator subagents trực tiếp trên masked queue.
- Cập nhật README EN/VI và test coverage cho template contract.

**Files thay đổi:**
- `docs/en/template/post-validation.md` — created
- `docs/vi/template/post-validation.md` — created
- `README.md`, `README.vi.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Split vẫn là CLI stage, chưa có MCP wrapper riêng.

**Flow explained:**
Sau three-model validation, agent dùng `run_consensus_pmi` để tạo consensus/PMI artifacts. Nếu không có flagged rows thì split trực tiếp `validated_dataset.csv`. Nếu có flagged rows thì agent rewrite chỉ các hypothesis bị PMI flag, chạy `apply-paraphrase`, revalidate changed rows bằng ba validator subagents, promote bằng `promote_paraphrase_revalidation`, rồi split publishable dataset cuối cùng.

---

### [2026-06-25 11:40] — [PromptRefinement] Add MCP evidence and editor-task helpers

**Đã làm:**
- Thêm service method tạo failed-round evidence pack cho prompt refinement.
- Expose MCP tool `prepare_prompt_refinement_evidence_pack`.
- Expose MCP tool `prepare_prompt_refinement_editor_tasks` để orchestrator lấy
  concrete payloads rồi spawn hai editor subagents.
- Evidence pack ghi `disagreement_rows.csv`, `disagreement_calibration_rows.csv`, `round_summary.json`, và snapshot current generator/validator instructions.
- Cập nhật templates, skill, instructor, README, validator flow docs, và feature plan để dùng tool mới thay vì chỉ mô tả future MCP.
- Thêm tests cho service output và MCP tool schema.

**Files thay đổi:**
- `backend/src/services/prompt_refinement_service.py` — modified
- `backend/src/providers/validation_provider.py` — modified
- `backend/src/schemas/validation_runtime_schema.py` — modified
- `backend/tests/test_prompt_refinement_service.py` — modified
- `backend/tests/test_validation_provider.py` — modified
- `backend/skills/prompt_refinement.md`, `backend/skills/instructor.md` — modified
- `docs/en/template/prompt-refinement.md`, `docs/vi/template/prompt-refinement.md` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `README.md`, `README.vi.md` — modified
- `docs/superpowers/plans/prompt-refinement-editor-candidates.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Backend vẫn không spawn validator/editor subagents và không auto-edit prompt; phần đó thuộc main agent/harness.

**Flow explained:**
Sau khi `evaluate_prompt_refinement_round` trả `decision=refine_prompt`, main agent gọi `prepare_prompt_refinement_evidence_pack` để backend build deterministic evidence pack từ calibration/verdict files và current prompt instructions. Sau đó main agent gọi `prepare_prompt_refinement_editor_tasks` để lấy hai task payload files, spawn editor subagents từ payload đó, chọn/apply một change, rerun validators, gọi evaluation round tiếp theo, và chỉ lock sau approval.

---

### [2026-06-25 11:05] — [PromptRefinement] Independent pass for editor-candidate guardrails

**Đã làm:**
- Review lại plan `prompt-refinement-editor-candidates` và đối chiếu các template EN/VI hiện có.
- Làm rõ ranh giới blind/non-blind: validator subagents phải luôn blind, editor subagents chỉ review failed round và chỉ trả proposal.
- Bổ sung test coverage cho template leakage guardrails và xác nhận main templates chỉ nêu đúng hai editor roles.
- Giữ nguyên backend runtime/service/schema; không đụng `backend/data/validation/validation_masked.csv`.

**Files thay đổi:**
- `docs/en/template/prompt-refinement.md` — modified
- `docs/vi/template/prompt-refinement.md` — modified
- `docs/en/template/prompt-refinement-editor-validator-rubric.md` — modified
- `docs/en/template/prompt-refinement-editor-generator-policy.md` — modified
- `docs/vi/template/prompt-refinement-editor-validator-rubric.md` — modified
- `docs/vi/template/prompt-refinement-editor-generator-policy.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None trong scope template/test của feature này.

**Flow explained:**
Prompt-refinement loop vẫn do main agent điều phối. Validator subagents chỉ nhận masked rows và không thấy label hay peer verdict. Sau khi kappa fail, editor subagents mới được review evidence pack có label để chẩn đoán failed round, nhưng output của họ vẫn chỉ là proposal nhỏ nhất cho một target duy nhất; main agent mới là bên chọn, apply, rerun validators, và gọi `evaluate_prompt_refinement_round`.

---

### [2026-06-25 00:15] — [PromptRefinement] Add editor-candidate auto-refine templates

**Đã làm:**
- Thêm 2 editor templates EN cho validator-rubric reviewer và generator-policy reviewer.
- Thêm 2 editor templates VI mirror cho cùng hai vai trò.
- Cập nhật prompt-refinement templates EN/VI với auto-refine loop sau `decision=refine_prompt`.
- Thêm evidence-pack convention `output_root/round-<NN>/evidence/`.
- Giữ rule: editor subagents chỉ trả proposal, không gọi MCP, không sửa file, không ghi runtime state, không evaluate, không lock.
- Cập nhật `skill://prompt_refinement` để mô tả evidence-pack, hai editor roles, proposal schema, và selection rules giống template.
- Thêm test coverage cho editor workflow và editor-template guardrails.

**Files thay đổi:**
- `docs/en/template/prompt-refinement-editor-validator-rubric.md` — created
- `docs/en/template/prompt-refinement-editor-generator-policy.md` — created
- `docs/vi/template/prompt-refinement-editor-validator-rubric.md` — created
- `docs/vi/template/prompt-refinement-editor-generator-policy.md` — created
- `docs/en/template/prompt-refinement.md` — modified
- `docs/vi/template/prompt-refinement.md` — modified
- `backend/skills/prompt_refinement.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None for editor-template guardrails. Backend auto-loop/spawn tooling remains intentionally out of scope.

**Flow explained:**
Khi một prompt-refinement round fail kappa, main agent tạo evidence pack từ artifacts của round đó, spawn đúng hai editor subagents để review validator rubric và generator policy, rồi chọn proposal nhỏ nhất có evidence tốt. Editor agents không được mutate state; main agent vẫn sở hữu apply, rerun validators, gọi `evaluate_prompt_refinement_round`, và xin approval trước khi lock.

---

### [2026-06-24 22:47] — [PromptRefinement] Remove local git commit logging from MLflow rounds

**Đã làm:**
- Bỏ param `git_commit` khỏi MLflow round logging vì không phải provenance ổn định giữa các máy/operator.
- Xoá helper `_git_commit()` và import `subprocess` không còn dùng.

**Files thay đổi:**
- `backend/src/services/prompt_refinement_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt refinement provenance dựa vào artifact thật của round: prompt registry versions, prompt bundle, verdict files, disagreement rows, model names, kappa và decision. Local git commit không còn được log vì mỗi operator có thể chạy từ checkout khác và tự commit thay đổi nếu cần.

---

### [2026-06-24 22:02] — [PromptRefinement] Generalize agent template and reduce filesystem leakage

**Đã làm:**
- Rút gọn prompt-refinement templates EN/VI thành template tổng quát với placeholders.
- Bỏ repo/path cụ thể và bỏ hướng dẫn agent tự start MLflow/server.
- Thêm guard MCP-first: chỉ đọc required resources, calibration_source được cung cấp, và không inspect file repo không liên quan.
- Điều chỉnh `skill://prompt_refinement` để nói theo instruction/resource thay vì hardcode file path như `backend/skills/validator.md`.

**Files thay đổi:**
- `docs/en/template/prompt-refinement.md` — modified
- `docs/vi/template/prompt-refinement.md` — modified
- `backend/skills/prompt_refinement.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Prompt refinement template giờ chỉ giao nhiệm vụ orchestration cho agent: dùng MCP resources, tạo calibration/verdict artifacts từ input đã cung cấp, gọi `evaluate_prompt_refinement_round`, và báo blocker nếu MCP/MLflow unavailable. Việc khởi động backend/MLflow thuộc operator, không nằm trong prompt dán cho agent.
