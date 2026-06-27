# NLI Synthetic Data Processing

Repo gồm backend FastAPI + FastMCP và frontend React để tạo, kiểm tra và xử lý
dataset Vietnamese NLI.

## Chạy local

Backend:

```bash
cd backend
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

MCP endpoint: `http://localhost:8000/mcp/`.

## Prompt refinement tùy chọn

MLflow không chạy chung với backend. Chỉ bật khi cần calibrate prompt:

```bash
cd backend
mkdir -p .mlflow/artifacts
uv run mlflow server \
  --backend-store-uri "sqlite:///$PWD/.mlflow/mlflow.db" \
  --default-artifact-root "file://$PWD/.mlflow/artifacts" \
  --host 127.0.0.1 \
  --port 5000
```

Mở `http://127.0.0.1:5000`, sau đó yêu cầu agent đọc
`skill://prompt_refinement`. Agent phải dùng cùng một calibration dataset, thu
đúng ba file verdict độc lập, rồi gọi `evaluate_prompt_refinement`.

- Fleiss' kappa `< 0.85`: calibration trả `needs_prompt_update`; harness có thể gọi
  `propose_prompt_refinement_update` để lấy proposal user-facing, rồi dừng để
  user tự update prompt nếu phù hợp.
- Fleiss' kappa `>= 0.85`: calibration trả `accepted`.
- Backend không register prompt version, promote alias, lock prompt, hoặc tự
  chạy calibration tiếp theo.

PMI không nằm trong refinement loop. PMI chạy sau generation và validation để
phát hiện artifact token cần paraphrase.

## MCP resources chính

| Resource | Mục đích |
|----------|----------|
| `skill://instructor` | Điểm bắt đầu và sơ đồ toàn pipeline |
| `skill://generator_plain` | Translate/naturalize cho source NLI đã có label |
| `skill://generator_adversarial` | Quy tắc adversarial generation có kiểm soát |
| `skill://generator` | Legacy adversarial generator alias |
| `skill://validator` | Blind validation 3 class |
| `skill://prompt_refinement` | Calibration ba model, kappa, và proposal user-facing |

Tài liệu chi tiết:

- [Generator flow](docs/vi/flow/generator.md)
- [Validator flow](docs/vi/flow/validator.md)
- [Post-validation template](docs/vi/template/post-validation.md)
- [Prompt refinement template](docs/vi/template/prompt-refinement.md)
- [Project overview](docs/vi/project-overview.md)
