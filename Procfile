backend: cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
mlflow: cd backend && uv run mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///$PWD/.mlflow/mlflow.db --default-artifact-root file://$PWD/.mlflow/artifacts
