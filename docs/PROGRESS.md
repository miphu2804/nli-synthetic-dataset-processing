### [2026-06-30 18:25] — [Templates] Require fresh generation workers per batch

**Đã làm:**
- Cập nhật generator templates EN/VI để mỗi Codex worker chỉ xử lý một claimed batch rồi bỏ context.
- Cập nhật `delegation` skill để main agent tạo worker context mới cho từng batch và không reuse worker qua nhiều batch nếu user chưa approve đổi mode.
- Việt hoá guide prose trong các template VI, giữ nguyên tool names, schema fields, command names, placeholders, và label names.
- Thêm regression test cho guardrail fresh-worker-per-batch.

**Files thay đổi:**
- `docs/en/template/generator.md` — modified
- `docs/vi/template/generator.md` — modified
- `docs/vi/template/validator.md` — modified
- `docs/vi/template/post-validation.md` — modified
- `docs/vi/template/prompt-refinement.md` — modified
- `backend/skills/delegation.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Generation runtime vẫn giữ nguyên MCP ownership: main agent claim, self-check, submit, verify, và finalize; worker chỉ nhận một claimed batch, trả JSON, rồi bị bỏ context. Rule này giảm context dài và tránh rows/checks từ batch trước leak sang quyết định batch sau mà không đổi logic tool.

---

### [2026-06-30 18:10] — [Docs] Add tmux runtime start commands

**Đã làm:**
- Cập nhật README EN/VI với hướng dẫn cài `tmux` cho macOS, Linux, và Windows qua WSL.
- Thêm lệnh chạy thủ công backend API và MLflow trong cùng `tmux` session để đóng terminal mà service vẫn chạy.
- Thêm lệnh chạy gộp backend API và MLflow bằng Honcho trong `tmux`.
- Ghi rõ cách refresh Honcho qua backend dev dependencies khi môi trường chưa có lệnh `honcho`.

**Files thay đổi:**
- `README.md` — modified
- `README.vi.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Local runtime docs giờ có hai mode chính thức trong `tmux`: chạy thủ công bằng hai window cho backend API và MLflow, hoặc chạy gộp bằng `uv --project backend run honcho start` từ repo root. Windows dùng WSL để có `tmux`; detach bằng `Ctrl-b` rồi `d`, attach lại bằng `tmux attach -t nli-runtime`, và tắt bằng `tmux kill-session -t nli-runtime`.

---

### [2026-06-30 17:28] — [Templates] Tighten interactive MCP orchestration

**Đã làm:**
- Cập nhật generator templates EN/VI để cấm local orchestration scripts, `fastmcp.Client` headless loops, `codex exec`, `claude -p`, subprocess workers, và đổi execution mode khi chưa được user approve.
- Cập nhật validator templates EN/VI để giữ `batch_size=20`, sửa input placeholder thành generated CSV có label để runtime tự mask, và khi payload bị truncate thì báo blocker thay vì giảm batch size.
- Cập nhật `delegation` và `execution` skills để định nghĩa subagent trong Codex Desktop là visible Codex worker, không phải CLI worker hoặc script ngoài.
- Thêm regression tests cho template/skill guardrails mới.

**Files thay đổi:**
- `docs/en/template/generator.md` — modified
- `docs/vi/template/generator.md` — modified
- `docs/en/template/validator.md` — modified
- `docs/vi/template/validator.md` — modified
- `backend/skills/delegation.md` — modified
- `backend/skills/execution.md` — modified
- `backend/tests/test_skill_service.py` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Default interactive flow giờ phải giữ MCP calls trong active Codex session và chỉ dùng visible Codex workers nếu cần subagents. Shell chỉ còn dùng cho inspection/debug nhẹ như `rg`, `sed`, `nl`, `wc`, `head`, `tail`, `ls`, `find`, `ps`, hoặc read-only progress checks; không dùng Bash/Python scripts để claim, transform, validate, submit, hoặc finalize runtime batches. Headless orchestration vẫn chỉ có thể là mode riêng nếu user approve rõ.

---

### [2026-06-30 09:57] — [Runtime] Add Honcho local start

**Đã làm:**
- Thêm `Procfile` để chạy backend FastAPI/FastMCP và MLflow server cùng một lệnh Honcho.
- Thêm `honcho` vào dev dependencies bằng `uv`.
- Đổi default MLflow URL local sang `http://127.0.0.1:5001` vì port 5000 đang bị process macOS chiếm trên máy này.
- Cập nhật README EN/VI để local start dùng `uv --project backend run honcho start`.
- Gỡ phần file-type converter khỏi README EN/VI surface; runtime API hiện tại không đổi.

**Files thay đổi:**
- `Procfile` — created
- `README.md` — modified
- `README.vi.md` — modified
- `backend/.env.example` — modified
- `backend/src/app_config.py` — modified
- `backend/pyproject.toml` — modified
- `backend/uv.lock` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Local dev giờ có một lệnh root-level để chạy cả backend và MLflow: `uv --project backend run honcho start`. `Procfile` giữ backend trên port 8000, MLflow trên `127.0.0.1:5001`, và MLflow state/artifacts nằm dưới `backend/.mlflow/` đã được gitignore. README không còn quảng bá converter file type; code convert CSV chưa bị xoá vì request chỉ chạm README/runtime start surface.

---

### [2026-06-30 09:46] — [Docs] Align README after frontend removal

**Đã làm:**
- Gỡ phần frontend khỏi README EN/VI sau khi frontend integration đã bị xoá.
- Cập nhật hướng dẫn Docker Compose thành backend-only.
- Xoá frontend service khỏi `docker-compose.yml` để compose build/push không trỏ vào thư mục frontend đã bị xoá.

**Files thay đổi:**
- `README.md` — modified
- `README.vi.md` — modified
- `docker-compose.yml` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Sau commit remove frontend integration, repo chỉ còn backend FastAPI + FastMCP. README và Compose giờ phản ánh đúng surface hiện tại: chạy backend bằng `uvicorn` hoặc `docker compose up --build`, không còn hướng dẫn `cd frontend`, `npm run dev`, image frontend, hay `VITE_API_ENDPOINT`.

---

### [2026-06-29 18:54] — [Validation] Tighten validator prompt template for truncated claims

**Đã làm:**
- Cập nhật validator templates EN/VI để phản ánh đúng blind-validation runtime hiện tại.
- Thêm guardrail cho trường hợp `claim_next_validation_batch` bị truncate hoặc trả payload không đầy đủ.
- Ghi rõ không được reconstruct batch từ source CSV hoặc `data/batches/{run_id}` vì runtime chỉ ghi batch CSV sau `submit_validation_result`.
- Chuẩn hóa khuyến nghị `batch_size` nhỏ và input/output placeholders theo convention per-model output.

**Files thay đổi:**
- `docs/en/template/validator.md` — modified
- `docs/vi/template/validator.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Validator template giờ nói đúng boundary của runtime hiện tại: `start_validation_run` nhận labeled generated CSV làm source of truth, `claim_next_validation_batch` chỉ trả masked rows qua tool response, và `data/batches/{run_id}` chưa có full claim artifact trước lúc submit. Nếu tool/chat truncate claim payload thì agent phải coi batch đó là unusable, release hoặc retry với `batch_size` nhỏ hơn, thay vì quay lại đọc source CSV để lấp phần bị thiếu.

---

### [2026-06-29 15:46] — [Drive] Remove Google Drive stub surface

**Đã làm:**
- Xoá Google Drive stub khỏi backend router/service/schema và test riêng.
- Gỡ Drive router khỏi FastAPI app để các route `/api/drive/*` không còn đi vào MCP surface sinh từ `FastMCP.from_fastapi(...)`.
- Xoá Google Drive page khỏi frontend, bỏ nav item, và dọn API client types/helpers.

**Files thay đổi:**
- `backend/src/routers/drive_router.py` — deleted
- `backend/src/services/drive_service.py` — deleted
- `backend/src/schemas/drive_schema.py` — deleted
- `backend/tests/test_drive_router.py` — deleted
- `backend/src/main.py`, `backend/src/services/__init__.py`, `backend/src/schemas/__init__.py` — modified
- `frontend/src/pages/GoogleDrive.tsx` — deleted
- `frontend/src/App.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/src/lib/api.ts` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Google Drive trước đó chỉ là stub module được mount qua FastAPI router và hiện trên frontend. Vì FastMCP được tạo từ FastAPI app sau khi include routers, bỏ `drive_router` khỏi `main.py` cũng loại các endpoint Drive khỏi MCP-derived route surface. Core NLI runtime, dataset IO, skill resources, generation/validation MCP tools, và post-validation flow không đổi.

---

### [2026-06-29 10:11] — [DataProcessing] Merge dataset IO service

**Đã làm:**
- Tạo `DataProcessingService` làm boundary duy nhất cho tabular file IO: read CSV/parquet window, write CSV/parquet rows, và convert common tabular inputs về CSV.
- Thêm schema/route `/api/datasets/convert-to-csv` cho `.csv`, `.tsv`, `.parquet`, `.xlsx`, `.xls`, `.jsonl`, và flat JSON record arrays.
- Đổi generation, validation, providers, routers, và tests sang dependency `DataProcessingService`.
- Xoá service split cũ `DatasetReaderService` / `DatasetWriterService`.
- Cập nhật README/project overview để nói rõ downstream stages vẫn dùng explicit CSV paths và conversion không random sampling, label cleanup, hay hidden runtime cleanup.

**Files thay đổi:**
- `backend/src/services/data_processing_service.py` — created
- `backend/src/services/dataset_reader_service.py`, `backend/src/services/dataset_writer_service.py` — deleted
- `backend/src/schemas/dataset_conversion_schema.py`, `backend/src/schemas/__init__.py` — created/modified
- `backend/src/services/base_run_service.py`, `backend/src/services/generation_run_service.py`, `backend/src/services/validation_run_service.py` — modified
- `backend/src/providers/generation_provider.py`, `backend/src/providers/validation_provider.py` — modified
- `backend/src/routers/reader_router.py`, `backend/src/routers/writer_router.py` — modified
- `backend/tests/test_dataset_io.py`, `backend/tests/test_generation_run_service.py`, `backend/tests/test_validation_run_service.py` — modified
- `README.md`, `README.vi.md`, `docs/en/project-overview.md`, `docs/vi/project-overview.md`, `docs/PROGRESS.md` — modified

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Data processing giờ là boundary file-level duy nhất. Generation/validation runtime vẫn gọi `read_dataset(...)` và `read_dataframe(...)` trên CSV/parquet paths, còn conversion sang CSV là bước rõ ràng qua API trước khi đưa file vào downstream stages. Service không chứa generation/validation policy, sampling policy, label normalization, PMI, split, hay cleanup ngoài việc ghi output CSV/parquet được yêu cầu.

---

### [2026-06-28 14:10] — [Validation] Finalize ANLI 1-1000 blind verdict artifacts

**Đã làm:**
- Verify `backend/data/generated/anli1-1000-from-sample-1.csv` parse được với 1000 rows rồi chuẩn hóa header CSV để runtime validation đọc đúng `source_uid,premise,hypothesis,label`.
- Tạo masked input `backend/data/generated/anli1-1000-from-sample-1_validation_masked.csv` với label rỗng cho validator-facing flow.
- Hoàn tất 3 validation runs `validation-20260628111418-27d77d7b`, `validation-20260628111418-6d50aaf0`, `validation-20260628111418-f7b97e02` và finalize thành `validation_results.csv` dưới `backend/data/validated/anli1-1000-from-sample-1/validator_{a,b,c}_medium/`.
- Reduce 3 finalized outputs về `backend/data/validated/anli1-1000-from-sample-1/verdicts/{validator_a_medium,validator_b_medium,validator_c_medium}.csv` với đúng schema `source_uid,predicted_label,reason`.
- Chạy integrity gate giữa generated input, masked input, và 3 verdict files; kết quả pass với 1000 rows/file, không duplicate `source_uid`, không blank reason, và chỉ có label canonical.

**Files thay đổi:**
- `backend/data/generated/anli1-1000-from-sample-1.csv` — created/normalized
- `backend/data/generated/anli1-1000-from-sample-1.pre-normalize.csv` — created
- `backend/data/generated/anli1-1000-from-sample-1_validation_masked.csv` — created
- `backend/data/validated/anli1-1000-from-sample-1/validator_a_medium/validation_results.csv` — created
- `backend/data/validated/anli1-1000-from-sample-1/validator_b_medium/validation_results.csv` — created
- `backend/data/validated/anli1-1000-from-sample-1/validator_c_medium/validation_results.csv` — created
- `backend/data/validated/anli1-1000-from-sample-1/verdicts/` — created
- `docs/PROGRESS.md` — updated

**Blockers:** Exact provenance audit for “all 1000 rows came from the same 3 Codex subagents end-to-end” would require a fresh rerun from scratch; this completion resumed existing mixed-worker run state and finished the remaining claims cleanly.

**Còn lại:** None for the current verdict artifacts and integrity handoff.

**Flow explained:**
Runtime validation vẫn dùng generated input có label làm source of truth và chỉ phát masked rows cho validator-facing work. Run state được resume từ `.pipeline/runs/*` + `data/batches/*`, submit nốt các claim còn active, finalize từng run thành `validation_results.csv`, rồi reduce xuống 3 verdict CSV phục vụ post-validation. Integrity gate phải so theo tập `source_uid` thực có trong generated/masked inputs, không giả định UID liên tiếp 1..1000 vì file này có 1000 rows nhưng UID kéo tới 1003.

---

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
