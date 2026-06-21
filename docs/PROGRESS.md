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

