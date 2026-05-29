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
  -d '{"path":"/absolute/path/to/file.csv","limit":5}'
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

## Translate dataset to Vietnamese

```bash
curl -X POST http://127.0.0.1:8000/api/datasets/translate \
  -H 'content-type: application/json' \
  -d '{
    "path":"/absolute/path/to/file.csv",
    "text_columns":["premise","hypothesis"],
    "batch_size":10
  }'
```
