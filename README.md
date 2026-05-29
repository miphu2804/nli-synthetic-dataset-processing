# Dataset Reader MCP Baseline

Minimal backend inspired by the `NexiraCopilot` backend structure:

- `src/app_config.py`: env/config
- `src/dataset_reader_service.py`: pandas facade for arbitrary datasets
- `src/mcp_server.py`: MCP adapter and tool registration
- `src/main.py`: FastAPI app mounting REST and MCP on the same port

## Run

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## REST smoke test

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/read \
  -H 'content-type: application/json' \
  -d '{"path":"/absolute/path/to/file.csv","batch_size":5,"batch_offset":0}'
```

## MCP

The MCP HTTP app is mounted under:

```text
/mcp
```

Tool name:

```text
read_dataset_with_pandas
```

Additional tool:

```text
translate_dataset_with_chatgpt
```

Additional tool:

```text
write_dataset_output
```

## Translate dataset to Vietnamese

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/translate \
  -H 'content-type: application/json' \
  -d '{
    "path":"/absolute/path/to/file.csv",
    "text_columns":["premise","hypothesis"],
    "batch_size":10,
    "output":{"format":"csv"}
  }'
```

If `OPENAI_API_KEY` is missing, `/translate` returns `status="pass_through"` plus rows for external translation via ChatGPT web/MCP tools. Persist the translated rows with:

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/write \
  -H 'content-type: application/json' \
  -d '{
    "rows":[{"premise":"A","premise_vi":"B"}],
    "output":{"format":"csv","path":"./outputs/demo.csv"}
  }'
```

For `output.format="google_drive"`, the server stages a local CSV and returns the staged path so a connected Google Drive MCP tool can upload it.
