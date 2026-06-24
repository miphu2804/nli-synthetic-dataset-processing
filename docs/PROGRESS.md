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

### [2026-06-22 05:20] — [ValidationIntegrity] Expose deterministic MCP wrappers

**Đã làm:**
- Thêm MCP wrapper `run_consensus_pmi` để gọi cùng contract deterministic của CLI `consensus-pmi` và trả row counts + artifact paths.
- Thêm MCP wrapper `promote_paraphrase_revalidation` để promote rewrites sau đúng ba verdict files revalidation.
- Thêm provider tests cho schema không leak `self` và runtime write artifacts cho cả consensus/PMI lẫn paraphrase promotion.
- Cập nhật validator flow docs EN/VI và status của fix plan 04.

**Files thay đổi:**
- `backend/src/providers/validation_provider.py` — modified
- `backend/tests/test_validation_provider.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/superpowers/plans/fix-04-deterministic-stage-mcp-wrappers.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Premise-grouped train/dev/test split vẫn chưa có CLI.

**Flow explained:**
MCP wrappers chỉ là transport adapters. Chúng không gọi model và không tự suy hidden labels; chúng discover đúng ba verdict files rồi gọi lại function CLI đã được test. `aggregate`, `pmi`, và `apply-paraphrase` vẫn là stage CLI/operator riêng, còn `consensus-pmi` và `promote-paraphrase` có thêm wrapper mỏng vì artifact contract đã ổn định.

---

### [2026-06-22 04:55] — [ValidationIntegrity] Add consensus PMI command

**Đã làm:**
- Thêm CLI `consensus-pmi` để chạy aggregate + PMI trong một bước và persist `validation_votes.csv`, `validated_dataset.csv`, `review_dataset.csv`, `pmi_artifact_tokens.csv`, `pmi_flagged_rows.csv`.
- Thêm default output convention `data/validated/<expected-input-stem>` khi operator không truyền `--output-dir`.
- Thêm tests cho default path, function output, và subcommand noninteractive.
- Cập nhật validator flow docs EN/VI và status của fix plan 03.

**Files thay đổi:**
- `backend/src/cli.py` — modified
- `backend/tests/test_cli.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/superpowers/plans/fix-03-persist-consensus-pmi-artifacts.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Chưa expose qua MCP; command này vẫn là operator-run deterministic stage.

**Flow explained:**
`consensus-pmi` không đổi rule consensus hay PMI. Nó chỉ gom hai bước đã có vào một entrypoint có output convention rõ, giúp handoff biết corpus đã có đủ artifacts trước khi paraphrase.

---

### [2026-06-22 04:35] — [ValidationIntegrity] Add paraphrase promotion CLI

**Đã làm:**
- Thêm utility `promote_revalidated_paraphrases()` để promote only rewrites được 2/3 revalidation verdicts giữ đúng trusted label.
- Thêm CLI `promote-paraphrase` nhận `paraphrased_dataset.csv`, `paraphrase_revalidation_masked.csv`, 3 verdict files, và trusted labels; xuất promoted dataset, revalidation votes, review/discard artifact.
- Thêm unit tests cho accept/reject/missing UID/duplicate UID/invalid label và CLI tests cho output + exact 3 verdict files.
- Cập nhật validator flow docs EN/VI và status của fix plan 02.

**Files thay đổi:**
- `backend/src/utils/validation_aggregation/promotion.py` — created
- `backend/src/utils/validation_aggregation/__init__.py` — modified
- `backend/src/cli.py` — modified
- `backend/tests/test_validation_aggregation.py` — modified
- `backend/tests/test_cli.py` — modified
- `docs/en/flow/validator.md`, `docs/vi/flow/validator.md` — modified
- `docs/superpowers/plans/fix-02-paraphrase-revalidation-promotion.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** MCP wrappers vẫn chưa expose stage này; làm sau khi artifact convention ổn định.

**Flow explained:**
`apply-paraphrase` vẫn chỉ tạo candidate và changed-row queue. `promote-paraphrase` là gate deterministic tiếp theo: aggregate đúng 3 verdict files trên changed rows, giữ rewrite có decision `keep`, loại `review/discard` khỏi publishable output, và ghi review artifact để người duyệt xử lý.

---

### [2026-06-22 04:08] — [Planning] Add ordered fix branch notes

**Đã làm:**
- Tạo 5 Markdown plan theo thứ tự nhánh fix: prompt lock/current HEAD, paraphrase revalidation promotion, persisted consensus/PMI artifacts, deterministic-stage MCP wrappers, premise-grouped split.
- Mỗi file nêu rõ problem, verified evidence, scope, out-of-scope, acceptance criteria, và verification command.

**Files thay đổi:**
- `docs/superpowers/plans/fix-01-prompt-lock-current-head.md` — created
- `docs/superpowers/plans/fix-02-paraphrase-revalidation-promotion.md` — created
- `docs/superpowers/plans/fix-03-persist-consensus-pmi-artifacts.md` — created
- `docs/superpowers/plans/fix-04-deterministic-stage-mcp-wrappers.md` — created
- `docs/superpowers/plans/fix-05-premise-grouped-split.md` — created
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** Chưa implement các fix; đây là handoff plan cho từng branch.

**Flow explained:**
Thứ tự fix đề xuất là: lock/rerun prompt trước khi generation lớn; đóng revalidation/promotion trước khi expose MCP wrapper; xác lập artifact output convention cho consensus/PMI; cuối cùng mới split dataset đã promoted. MCP wrappers phụ thuộc vào CLI/service contract đã ổn định, nên không nên làm trước revalidation/promotion.

---

### [2026-06-20 16:00] — [PromptRefinement] Hard-khoá provenance + lock bundle (codex round 4)

**Đã làm:**
- Review flow refinement + MLflow tracing cùng codex CLI (gpt-5.5 xhigh). Triage 7 finding theo threat model local single-operator; chốt làm các mục thật/rẻ.
- Skill: thêm section "Round Integrity (prompt provenance)" — cấm sửa `generator.md`/`validator.md` giữa lúc dispatch subagent và `evaluate_round`; nói rõ MLflow Prompt Registry đã version sẵn nên không giữ file `.md` version song song thủ công.
- `confirm_prompt_lock`: thay `_parse_prompt_version` → `_parse_prompt_uri(uri, expected_name)` validate đúng dạng `prompts:/<name>/<version>` bằng regex + version ≥ 1 (chặn URI tamper/malformed lock nhầm prompt/version).
- `confirm_prompt_lock`: 2 lệnh set `locked` alias không còn độc lập âm thầm — nếu lệnh validator fail sau generator → raise RuntimeError báo bundle inconsistent (re-run idempotent để sửa).
- Đảo thứ tự: set parent `session_locked` TRƯỚC child `lock_confirmed` (tránh báo confirmed khi session vẫn reuse được).
- Tên prompt rút thành constant `GENERATOR_PROMPT_NAME`/`VALIDATOR_PROMPT_NAME`.
- Thêm 2 test: parse URI malformed (8 ca) + partial locked-alias write raise & repairable. Tổng 18/18 pass. Codex round cuối: clean, no remaining bug.

**Files thay đổi:**
- `backend/skills/prompt_refinement.md` — modified (+16, section provenance)
- `backend/src/services/prompt_refinement_service.py` — modified (constants, _parse_prompt_uri regex, atomic-ish lock, reorder markers)
- `backend/tests/test_prompt_refinement_service.py` — modified (+2 tests)

**Blockers:** None

**Còn lại:** Các finding concurrency/interleaving (#4 race _resolve_session_run, #6 snapshot input files) cố ý KHÔNG làm — không xảy ra trong flow tuần tự local single-operator; fix sẽ thêm complexity vô ích.

**Flow explained:**
Layer 0 calibration: 3 verdict files → Fleiss kappa → register gen/val prompt vào MLflow Prompt Registry → 1 run/round (params+metrics+artifacts) → optional parent session run gom kappa trend → kappa≥0.85 = eligible_to_lock → `confirm_prompt_lock(lock_run_id)` set alias `locked` đúng version đã evaluate (đọc từ run params, KHÔNG đăng ký version mới). Lock-by-reference cho phép sửa file sau khi eligible mà vẫn khoá đúng version đã kappa-verified.

---

### [2026-06-19 22:30] — [Utils] Split validation_aggregation into a package

**Đã làm:**
- Tách `validation_aggregation.py` (653 dòng, 5 trách nhiệm) thành package cùng tên, giữ nguyên import path → không đụng call site (`cli.py`, `prompt_refinement_service.py`, tests).
- Module theo capability: `model_labels.py` (nạp/merge nhãn — nền chia sẻ), `voting.py` (vote consensus), `agreement.py` (Fleiss' kappa), `dataset_builders.py` (keep/review), `pmi.py` (PMI artifact + paraphrase, self-contained).
- `__init__.py` re-export 8 hàm public (`__all__`). Đồ thị import 1 chiều, không cycle.
- Verify: tập 20 def top-level giống hệt bản cũ; body hàm verbatim (diff chỉ là dòng nối import do black); `126 passed`; smoke import 8 hàm ok; isort/black sạch.

**Files thay đổi:**
- `backend/src/utils/validation_aggregation.py` — deleted
- `backend/src/utils/validation_aggregation/{__init__,model_labels,voting,agreement,dataset_builders,pmi}.py` — created

**Blockers:** None

**Còn lại:** None. `nli_labels.py` (30) + `validation_masking.py` (51) giữ nguyên (nhỏ, cohesive).

**Flow explained:**
Chỉ tổ chức lại, không đổi behavior. Dùng package + re-export thay vì sửa import ở 3 nơi → rủi ro thấp nhất, an toàn nhờ `test_validation_aggregation.py` + `test_cli.py`. Nhánh `refactor/validation-aggregation-split` tách từ `staging`.

---

### [2026-06-19 22:10] — [MCPProvider] Self-registering ToolProvider (unify tool registration)

**Đã làm:**
- Tạo base `ToolProvider`: `register(mcp)` tự quét method gắn `@tool` (marker `__fastmcp__`) và gọi `mcp.add_tool` — bỏ toàn bộ list `add_tool` thủ công.
- Đưa `sample_range_to_offset_limit` (1-based → 0-based, có guard `to_sample >= from_sample`) lên base làm bản dùng chung.
- Migrate cả 3 provider (generation, validation, dispatch_planning) sang kế thừa `ToolProvider`; xoá 2 bản copy `_sample_range_to_offset_limit` (validation trước đó thiếu guard).
- Thay 18 dòng `mcp.add_tool(...)` rải rác bằng `provider.register(mcp)` ở mỗi `register_*_tools`. `main.py` không đổi.
- Verify độc lập: `126 passed`; smoke `list_tools()` = 32 tool (đúng baseline), đủ 18/18 tool; isort/black sạch.

**Files thay đổi:**
- `backend/src/providers/base.py` — created
- `backend/src/providers/generation_provider.py`, `validation_provider.py`, `dispatch_planning_provider.py` — modified

**Blockers:** None

**Còn lại:** Trục 2 (composition root cho service) — đã quyết KHÔNG làm vì service stateless (YAGNI). Plan kế: refactor tách `validation_aggregation.py` (653 dòng, 5 trách nhiệm).

**Flow explained:**
Service = business logic; Provider = hợp đồng MCP (tên/mô tả/schema tham số) + dịch biên 1-based→0-based + `.model_dump`. Phần phân mảnh thật là "đăng ký": mỗi tool phải vừa viết method `@tool` vừa nhớ thêm `mcp.add_tool` — quên là tool biến mất im lặng. `ToolProvider.register` quét `__fastmcp__` (đã verify FastMCP 3.3.1 giữ marker khi bind method) nên thêm tool mới chỉ cần 1 method. Phần forward (`self._service.x().model_dump`) giống hình dạng giữa gen/val nhưng gọi service khác → cố ý không gom.

---
