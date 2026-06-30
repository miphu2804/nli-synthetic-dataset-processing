backend: cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
mlflow: cd backend && uv run mlflow server --host 127.0.0.1 --port 5001 --backend-store-uri sqlite:///$PWD/.mlflow/mlflow.db --default-artifact-root file://$PWD/.mlflow/artifacts
