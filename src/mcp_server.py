import logging

from fastmcp import FastMCP

from src.app_config import app_config
from src.dataset_reader_service import DatasetReaderService
from src.dataset_translate_schema import DatasetTranslateRequest
from src.openai_translation_service import OpenAITranslationService


class MCPAdapter:
    """Registers baseline MCP tools and exposes an ASGI app."""

    def __init__(
        self,
        dataset_reader_service: DatasetReaderService,
        translation_service: OpenAITranslationService,
        server_name: str | None = None,
    ):
        self._dataset_reader_service = dataset_reader_service
        self._translation_service = translation_service
        self._server_name = server_name or app_config.MCP_SERVER_NAME
        self._logger = logging.getLogger(__name__)
        self.mcp = FastMCP(self._server_name)
        self._register_tools()

    def _register_tools(self) -> None:
        @self.mcp.tool(
            name="read_dataset_with_pandas",
            description="Read a local dataset file with pandas and return schema, row counts, null counts, and preview rows.",
        )
        def read_dataset_with_pandas(
            path: str,
            limit: int = app_config.DEFAULT_PREVIEW_ROWS,
            sample_rows: int = app_config.DEFAULT_SAMPLE_ROWS,
            sheet_name: str | int | None = None,
            sep: str | None = None,
        ) -> dict:
            result = self._dataset_reader_service.read_dataset(
                path=path,
                limit=limit,
                sample_rows=sample_rows,
                sheet_name=sheet_name,
                sep=sep,
            )
            return result.model_dump()

        @self.mcp.tool(
            name="translate_dataset_with_chatgpt",
            description="Translate selected dataset columns into Vietnamese with OpenAI and write the result to CSV.",
        )
        async def translate_dataset_with_chatgpt(
            path: str,
            output_path: str | None = None,
            text_columns: list[str] | None = None,
            target_language: str = "Vietnamese",
            batch_size: int = 10,
            model: str | None = None,
            limit_rows: int | None = None,
        ) -> dict:
            request = DatasetTranslateRequest(
                path=path,
                output_path=output_path,
                text_columns=text_columns or ["premise", "hypothesis"],
                target_language=target_language,
                batch_size=batch_size,
                model=model,
                limit_rows=limit_rows,
            )
            result = await self._translation_service.translate_dataset(request)
            return result.model_dump()

        self._logger.info(
            "Registered MCP tools: read_dataset_with_pandas, translate_dataset_with_chatgpt"
        )

    def http_app(self):
        return self.mcp.http_app(path="/")
