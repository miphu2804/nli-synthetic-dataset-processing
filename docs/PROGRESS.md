### [2026-07-01 23:57] — [Runtime] Add CSV artifact batch submission

**Đã làm:**
- Thêm worker artifact targets vào generation/validation claim responses để main agent cấp sẵn path ghi CSV cho từng batch.
- Thêm MCP/runtime methods `submit_batch_result_from_artifacts` và `submit_validation_result_from_artifact` để backend tự đọc CSV, validate lại bằng schema hiện có, rồi commit batch theo progress flow cũ.
- Giữ nguyên inline submit APIs để backward-compatible; canonical merge/finalize vẫn ở runtime service.
- Cập nhật generator/validator templates, `delegation`, `execution`, `instructor`, và overview/flow docs để đổi contract từ “trả full JSON batch” sang “ghi CSV artifact + tiny JSON ack”.
- Căn lại generator templates EN/VI theo skeleton prompt của harness hiện tại: phần tools/goal/flow/rules bám mẫu main-agent prompt, còn artifact CSV được chèn trực tiếp vào flow/rules bằng placeholder.
- Sửa `SkillService` dùng `backend/skills` ổn định thay vì phụ thuộc cwd, nhờ đó skill/template verification tests chạy đúng.

**Files thay đổi:**
- `backend/src/schemas/generation_runtime_schema.py` — modified
- `backend/src/schemas/validation_runtime_schema.py` — modified
- `backend/src/services/base_run_service.py` — modified
- `backend/src/services/generation_run_service.py` — modified
- `backend/src/services/validation_run_service.py` — modified
- `backend/src/services/progress_tracking_service.py` — modified
- `backend/src/services/skill_service.py` — modified
- `backend/src/providers/generation_provider.py` — modified
- `backend/src/providers/validation_provider.py` — modified
- `backend/tests/test_generation_run_service.py`, `backend/tests/test_validation_run_service.py`, `backend/tests/test_generation_provider.py`, `backend/tests/test_validation_provider.py`, `backend/tests/test_skill_service.py` — modified
- `backend/skills/delegation.md`, `backend/skills/execution.md`, `backend/skills/instructor.md` — modified
- `docs/en/template/generator.md`, `docs/en/template/validator.md`, `docs/vi/template/generator.md`, `docs/vi/template/validator.md` — modified
- `docs/en/flow/generator.md`, `docs/vi/flow/generator.md`, `docs/en/project-overview.md`, `docs/vi/project-overview.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Main agent vẫn là owner của claim/submit/finalize và chỉ runtime mới mutate progress. Điểm mới là mỗi claimed batch giờ trả thêm `artifact_targets` nằm dưới run state để worker ghi `rows/verdicts` CSV cục bộ. Worker chỉ cần trả tiny JSON ack với path/count; main agent kiểm tra artifact rồi gọi submit-from-artifact. Backend đọc CSV artifact, chạy lại validation hiện có cho coverage/schema/label fidelity, sau đó mới ghi canonical batch CSV vào `data/batches/{run_id}` và append progress events. Finalize/merge không đổi, nên artifact mode chỉ thay batch handoff chứ không thay lifecycle.

---

### [2026-07-01 00:10] — [Docker] Align Honcho container startup

**Đã làm:**
- Đồng bộ root `Procfile` để MLflow serve trên `0.0.0.0:5000`.
- Cập nhật README EN/VI: Honcho là runtime dependency, Docker command map cả `8000` và `5000`, đồng thời mount `$HOME/Downloads:/downloads`.
- Ghi rõ container path cho MCP dataset input/output khi dùng Downloads mount.

**Files thay đổi:**
- `Procfile` — modified
- `README.md` — modified
- `README.vi.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Docker image đã dùng `backend/Procfile` để chạy Honcho cho FastAPI/FastMCP và MLflow, còn root `Procfile` phục vụ local Honcho từ repo root. Cả hai đều giữ MLflow ở port `5000`. Published Docker command cần `-p 5000:5000` để host thấy MLflow và `-v "$HOME/Downloads:/downloads"` để MCP runtime nhìn thấy dataset host qua `/downloads/...`. Smoke test image local đã xác nhận backend health, MCP status, MLflow HTTP 200, và mounted Downloads dataset path.

---

### [2026-06-30 19:27] — [DataRoot] Move runtime data to repo root

**Đã làm:**
- Chuyển tracked datasets từ `backend/data/` sang repo-root `data/`.
- Thêm path helper để `data/...` và `.pipeline/...` resolve ổn định khi chạy từ repo root, từ `backend/`, hoặc trong Docker `/app`.
- Đổi generation, validation, dataset reader, CLI discovery, aggregation defaults, và progress tracking sang repo-root `data/`.
- Preserve runtime batch artifact chưa tracked bằng cách move `backend/data/batches/...` sang `data/batches/...`.
- Cập nhật README/project overview/progress-tracking docs EN/VI để nói rõ `data/` nằm cùng cấp `backend/`.

**Files thay đổi:**
- `data/` — moved tracked datasets from `backend/data/`
- `.gitignore` — modified
- `backend/src/utils/project_paths.py` — created
- `backend/src/services/data_processing_service.py` — modified
- `backend/src/services/progress_tracking_service.py` — modified
- `backend/src/services/generation_run_service.py` — modified
- `backend/src/services/validation_run_service.py` — modified
- `backend/src/services/post_validation/validation_aggregation.py` — modified
- `backend/src/routers/reader_router.py` — modified
- `backend/src/cli.py` — modified
- `backend/tests/test_dataset_io.py`, `backend/tests/test_cli.py` — modified
- `README.md`, `README.vi.md`, `docs/en/project-overview.md`, `docs/vi/project-overview.md`, `docs/en/flow/progress-tracking.md`, `docs/vi/flow/progress-tracking.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Repo-root `data/` is now the canonical dataset/artifact root. `DataProcessingService` still owns only file-level tabular IO; generation/validation services still own run lifecycle and finalization. Relative runtime paths beginning with `data/` resolve through the project root, so local commands run from `backend/` and Docker commands run from `/app` target the same conceptual layout. Default progress state also resolves to repo-root `.pipeline`, and batch files live under repo-root `data/batches/{run_id}`.

---

### [2026-06-30 19:17] — [Docker] Allow MLflow published-port access

**Đã làm:**
- Chẩn đoán log image: MLflow đã bind `0.0.0.0:5000`, nhưng MLflow 3.14 security middleware vẫn kiểm tra Host/CORS.
- Cập nhật `backend/Procfile` để container MLflow cho phép truy cập qua published Docker port trong local development.
- Cập nhật README EN/VI để ghi rõ published image mở MLflow qua port `5000`.

**Files thay đổi:**
- `backend/Procfile` — modified
- `README.md` — modified
- `README.vi.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** Local Docker daemon is unavailable on this machine, so final image proof must come from GitHub Actions build-and-push.

**Còn lại:** None

**Flow explained:**
`--host 0.0.0.0` chỉ làm MLflow listen trên mọi interface trong container; MLflow 3.14 vẫn bật security middleware để validate Host header và CORS. Published Docker image là local-dev runtime, nên container Procfile thêm `--allowed-hosts '*'` và `--cors-allowed-origins '*'` cho MLflow để browser/agent truy cập được qua `http://localhost:5000` sau `-p 5000:5000`.

---

### [2026-06-30 19:06] — [Docker] Run MCP and MLflow in one image

**Đã làm:**
- Đổi backend Docker image sang chạy Honcho để start cả FastAPI/FastMCP và MLflow.
- Thêm `backend/Procfile` container-native với MCP trên `0.0.0.0:8000` và MLflow trên `0.0.0.0:5000`.
- Expose/map thêm port `5000` trong Dockerfile và Docker Compose.
- Đưa `honcho` vào runtime dependencies để image pull về chạy được mặc định.
- Cập nhật README EN/VI với Docker run command, MCP/MLflow endpoints, và boundary khi không mount volume.
- Thêm Docker MCP endpoint hint vào generator/validator templates EN/VI.

**Files thay đổi:**
- `backend/Dockerfile` — modified
- `backend/Procfile` — created
- `backend/pyproject.toml` — modified
- `backend/uv.lock` — modified
- `docker-compose.yml` — modified
- `README.md` — modified
- `README.vi.md` — modified
- `docs/en/template/generator.md` — modified
- `docs/en/template/validator.md` — modified
- `docs/vi/template/generator.md` — modified
- `docs/vi/template/validator.md` — modified
- `docs/PROGRESS.md` — updated

**Blockers:** None

**Còn lại:** None

**Flow explained:**
Docker runtime giờ không cần `tmux`; container dùng Honcho làm process supervisor đơn giản cho backend API/MCP và MLflow. Agent connection mặc định là `http://localhost:8000/mcp/`, MLflow là `http://localhost:5000`. Không mount volume vẫn ghi được progress, batch CSV, finalized outputs, và MLflow artifacts trong filesystem container; các artifact này là container-local và mất khi container bị xoá. Input dataset path phải tồn tại trong container, ví dụ do API/MCP tạo hoặc do custom image bake sẵn.

---

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
- Đổi default MLflow URL local sang `http://127.0.0.1:5000`.
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
Local dev giờ có một lệnh root-level để chạy cả backend và MLflow: `uv --project backend run honcho start`. `Procfile` giữ backend trên port 8000, MLflow trên `127.0.0.1:5000`, và MLflow state/artifacts nằm dưới `backend/.mlflow/` đã được gitignore. README không còn quảng bá converter file type; code convert CSV chưa bị xoá vì request chỉ chạm README/runtime start surface.

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
