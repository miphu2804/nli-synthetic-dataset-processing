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

## Boundary dataset

Boundary dataset nhận các input tabular phổ biến và convert về CSV canonical
trước khi đưa vào các phase sau. Dùng `/api/datasets/convert-to-csv` cho
`.csv`, `.tsv`, `.parquet`, `.xlsx`, `.xls`, `.jsonl`, hoặc JSON array record
phẳng. Generation, validation, và post-validation vẫn chạy trên path CSV rõ
ràng. Conversion không random sampling, không normalize label, không cleanup dữ
liệu, và không cleanup runtime artifact.

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
