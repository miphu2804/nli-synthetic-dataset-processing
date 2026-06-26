from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    TRANSLATION_MODEL: Optional[str] = None
    MLFLOW_URL: str = "http://127.0.0.1:5000"
    MLFLOW_EXPERIMENT_NAME: str = "nli-prompt-calibration"
    MLFLOW_ARTIFACT_ROOT: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app_config = AppConfig()
