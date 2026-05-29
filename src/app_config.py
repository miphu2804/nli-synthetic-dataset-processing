from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    APP_NAME: str = "dataset-reader-baseline"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    MCP_SERVER_NAME: str = "dataset-reader-mcp"
    MCP_MOUNT_PATH: str = "/mcp"
    DEFAULT_PREVIEW_ROWS: int = 5
    DEFAULT_SAMPLE_ROWS: int = 1000
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TRANSLATION_MODEL: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app_config = AppConfig()
