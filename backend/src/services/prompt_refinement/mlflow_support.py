from __future__ import annotations

import mlflow
from mlflow import MlflowClient

GENERATOR_PROMPT_NAME = "nli-generator"
VALIDATOR_PROMPT_NAME = "nli-validator"


def create_mlflow_client(tracking_uri: str) -> MlflowClient:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    return MlflowClient(
        tracking_uri=tracking_uri,
        registry_uri=tracking_uri,
    )
