# NLI Synthetic Data Processing

Repo gồm backend FastAPI + FastMCP để tạo, kiểm tra và xử lý dataset
Vietnamese NLI.

## Chạy local

Cài dependency backend một lần:

```bash
cd backend
uv sync
cd ..
```

Cài `tmux` nếu máy chưa có:

```bash
# macOS
brew install tmux

# Debian/Ubuntu/WSL
sudo apt update && sudo apt install tmux

# Fedora
sudo dnf install tmux
```

Trên Windows, chạy các lệnh này trong WSL. PowerShell native không có `tmux`.

Honcho là dev dependency của backend. Nếu
`uv --project backend run honcho --version` không chạy, refresh môi trường
backend:

```bash
cd backend
uv sync --dev
cd ..
```

### Chạy thủ công trong tmux

Dùng cách này khi muốn chạy riêng hai service. Giữ cả hai lệnh trong cùng một
`tmux` session để đóng terminal mà service vẫn chạy.

```bash
tmux new -s nli-runtime
```

Trong `tmux` session đó, chạy backend API:

```bash
cd backend
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Trong một `tmux` window khác, chạy MLflow:

```bash
# bấm Ctrl-b rồi c trước
cd backend
uv run mlflow server \
  --host 127.0.0.1 \
  --port 5001 \
  --backend-store-uri sqlite:///$PWD/.mlflow/mlflow.db \
  --default-artifact-root file://$PWD/.mlflow/artifacts
```

Detach mà không tắt service: bấm `Ctrl-b`, rồi `d`.
Kết nối lại sau:

```bash
tmux attach -t nli-runtime
```

Tắt cả hai service:

```bash
tmux kill-session -t nli-runtime
```

### Chạy gộp bằng Honcho trong tmux

Chạy backend và MLflow cùng một lệnh từ repo root:

```bash
tmux new -s nli-runtime
```

Trong `tmux` session đó, chạy Honcho:

```bash
uv --project backend run honcho start
```

Backend: `http://localhost:8000`
MCP endpoint: `http://localhost:8000/mcp/`
MLflow: `http://127.0.0.1:5001`

Detach bằng `Ctrl-b`, rồi `d`; kết nối lại bằng
`tmux attach -t nli-runtime`.

## Prompt refinement tùy chọn

Chạy trước large-scale generation khi generator policy hoặc validator rubric
cần calibration. Trong workflow agent đã connect sẵn, agent đã thấy MCP tools
và skill lookup của `nli-tools`. Agent load `prompt_refinement`, chuẩn bị một
calibration dataset cố định, thu đúng ba file verdict độc lập, rồi gọi
`evaluate_prompt_refinement`.

- Fleiss' kappa `< 0.85`: calibration trả `needs_prompt_update`; main agent đọc
  evidence đã log như `disagreement_rows.csv`, rồi report next step nhỏ nhất có
  evidence để user duyệt.
- Fleiss' kappa `>= 0.85`: calibration trả `accepted`.
- Backend log calibration evidence nhưng không propose prompt edit, register
  prompt version, promote alias, lock prompt, hoặc tự chạy calibration tiếp theo.

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
| `skill://prompt_refinement` | Calibration ba model, kappa, và evidence handoff cho agent |

Tài liệu chi tiết:

- [Generator flow](docs/vi/flow/generator.md)
- [Validator flow](docs/vi/flow/validator.md)
- [Post-validation template](docs/vi/template/post-validation.md)
- [Prompt refinement template](docs/vi/template/prompt-refinement.md)
- [Project overview](docs/vi/project-overview.md)
