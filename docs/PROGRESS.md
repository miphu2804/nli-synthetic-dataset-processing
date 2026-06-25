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
Prompt refinement provenance giờ dựa vào artifact thật của round: calibration dataset hash, prompt registry versions, prompt bundle, verdict files, disagreement rows, model names, kappa và decision. Local git commit không còn được log vì mỗi operator có thể chạy từ checkout khác và tự commit thay đổi nếu cần.

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

---

### [2026-06-24 00:00] — [ValidationIntegrity] Blank validator label payloads

**Đã làm:**
- Đổi validator-facing payload từ `masked_label=[MASK]` sang cột `label` có giá trị rỗng.
- Giữ trusted input/runtime vẫn cần expected `label` thật để chấm `predicted_label`.
- Đổi apply-paraphrase revalidation queue sang `source_uid,premise,hypothesis,label` với label rỗng.
- Đổi promotion check để reject mọi label thật trong revalidation queue, nhưng chấp nhận ô trống/NaN khi đọc CSV.
- Cập nhật validator skill, provider descriptions, docs/templates EN/VI, và tests theo contract mới.

**Files thay đổi:**
- `backend/src/utils/validation_masking.py`, `backend/src/schemas/validation_runtime_schema.py`, `backend/src/services/validation_run_service.py` — modified
- `backend/src/cli.py`, `backend/src/providers/validation_provider.py`, `backend/src/utils/validation_aggregation/promotion.py` — modified
- `backend/skills/validator.md`, `backend/skills/instructor.md` — modified
- `backend/tests/*validation*`, `backend/tests/test_cli.py`, `backend/tests/test_skill_service.py` — modified
- `docs/en/*`, `docs/vi/*`, `docs/PROGRESS.md` — modified

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Input cho `start_validation_run` vẫn phải là dataset có label thật; runtime dùng label đó làm hidden expected label khi submit/finalize. Chỉ payload/file giao cho validator mới có `label` rỗng để tránh lộ đáp án và tránh sentinel `[MASK]`. File `*_validation_masked.csv` giữ tên cũ vì downstream đang dùng tên này, nhưng nội dung masked giờ là blank label.

---

### [2026-06-23 19:49] — [GeneratorPolicy] Split plain and adversarial generator skills

**Đã làm:**
- Thêm `generator_plain.md` cho ANLI/source đã có quan hệ NLI-adversarial: translate/naturalize, giữ relation và label, không thêm adversarial transform mới.
- Thêm `generator_adversarial.md` cho controlled adversarial generation, giữ rule catalog cũ.
- Giữ `generator.md` làm legacy adversarial alias để không gãy prompt/harness cũ.
- Cập nhật `instructor`, `delegation`, README, flow/template docs EN/VI để agent chọn đúng một generation policy.
- Thêm `generator_skill_name` cho `evaluate_prompt_refinement_round` để MLflow version đúng generator policy được dùng trong calibration.
- Thêm tests cho skill split, provider schema, và prompt-refinement versioning theo selected generator skill.

**Files thay đổi:**
- `backend/skills/generator_plain.md` — created
- `backend/skills/generator_adversarial.md` — created
- `backend/skills/generator.md`, `backend/skills/instructor.md`, `backend/skills/delegation.md`, `backend/skills/prompt_refinement.md` — modified
- `backend/src/providers/validation_provider.py`, `backend/src/services/prompt_refinement_service.py` — modified
- `backend/tests/test_skill_service.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_prompt_refinement_service.py` — modified
- `README.md`, `README.vi.md`, `docs/en/*`, `docs/vi/*`, `docs/superpowers/specs/2026-06-19-prompt-refinement-mlflow-design.md` — modified

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Generation runtime vẫn giữ lifecycle MCP cũ (`start_generation_run` → claim/submit → verify/finalize). Khác biệt nằm ở policy markdown agent đọc trước khi transform: `generator_plain` cho ANLI/already-adversarial source để tránh double-adversarial label drift; `generator_adversarial` cho tạo biến thể mới có kiểm soát. Prompt refinement nhận `generator_skill_name` để snapshot đúng policy vào MLflow thay vì luôn hardcode `generator.md`.

---

### [2026-06-22 05:45] — [ValidationIntegrity] Add premise-grouped split CLI

**Đã làm:**
- Thêm utility split deterministic theo `premise`/group column để mọi hypothesis cùng premise không crossing giữa train/dev/test.
- Thêm CLI `split` với input/output dir, seed, ratio args; ghi `train.csv`, `dev.csv`, `test.csv`, và `split_manifest.json`.
- Manifest ghi seed, ratios, row/group counts, và label distribution từng split.
- Thêm tests cho grouping, deterministic seed, small dataset, invalid ratios, và CLI output.
- Cập nhật validator flow docs EN/VI và status của fix plan 05.

**Files thay đổi:**
- `backend/src/utils/dataset_split.py` — created
- `backend/src/cli.py` — modified
- `backend/tests/test_dataset_split.py` — created
- `backend/tests/test_cli.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/superpowers/plans/fix-05-premise-grouped-split.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None trong chuỗi 5 fix branch đã lập từ issue Markdown.

**Flow explained:**
Split là stage cuối sau `promoted_dataset.csv` hoặc `validated_dataset.csv` publishable. Thuật toán shuffle premise groups bằng seed cố định, assign theo row targets, rồi backfill split rỗng cho small datasets khi đủ group. Output giữ row order gốc trong từng split và manifest đủ để audit distribution.

---
