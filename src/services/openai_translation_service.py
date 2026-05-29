import json
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from src.app_config import app_config
from src.schemas import (
    DatasetTranslateRequest,
    DatasetTranslateResponse,
    DatasetWriteRequest,
)
from src.services.dataset_writer_service import DatasetWriterService


class OpenAITranslationService:
    """Translate dataset text columns or return pass-through rows for MCP/web flows."""

    def __init__(self, dataset_writer_service: DatasetWriterService | None = None):
        self._dataset_writer_service = dataset_writer_service or DatasetWriterService()

    async def translate_dataset(
        self,
        request: DatasetTranslateRequest,
    ) -> DatasetTranslateResponse:
        resolved_input = Path(request.path).expanduser().resolve()
        if not resolved_input.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_input}")

        dataframe = self._load_dataframe(resolved_input)
        if request.limit_rows:
            dataframe = dataframe.head(request.limit_rows).copy()
        else:
            dataframe = dataframe.copy()

        self._validate_text_columns(dataframe, request.text_columns)
        for column in request.text_columns:
            dataframe[f"{column}_vi"] = None

        if not app_config.OPENAI_API_KEY:
            return DatasetTranslateResponse(
                status="pass_through",
                input_path=str(resolved_input),
                output_format=request.output.format,
                output_path=self._default_output_path(resolved_input, request),
                rows_processed=int(len(dataframe)),
                translated_columns=[f"{column}_vi" for column in request.text_columns],
                rows=self._build_pass_through_rows(dataframe, request.text_columns),
                message=(
                    "OPENAI_API_KEY is missing. Translate these rows via ChatGPT web/MCP tools, then call write_dataset_output."
                ),
            )

        model_name = request.model or app_config.OPENAI_TRANSLATION_MODEL
        async with httpx.AsyncClient(
            base_url=app_config.OPENAI_BASE_URL,
            timeout=120,
            headers={
                "Authorization": f"Bearer {app_config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        ) as client:
            for start in range(0, len(dataframe), request.batch_size):
                batch = dataframe.iloc[start : start + request.batch_size]
                translated_rows = await self._translate_batch(
                    client=client,
                    rows=batch,
                    text_columns=request.text_columns,
                    target_language=request.target_language,
                    model_name=model_name,
                )
                for row_index, translations in translated_rows.items():
                    for column_name, translated_text in translations.items():
                        dataframe.at[row_index, f"{column_name}_vi"] = translated_text

        write_result = self._dataset_writer_service.write_dataset(
            request=self._build_write_request(
                dataframe=dataframe,
                request=request,
                resolved_input=resolved_input,
            )
        )

        return DatasetTranslateResponse(
            input_path=str(resolved_input),
            status="completed",
            output_format=request.output.format,
            output_path=write_result.output_path,
            rows_processed=int(len(dataframe)),
            translated_columns=[f"{column}_vi" for column in request.text_columns],
            model=model_name,
            message=write_result.message,
        )

    def _load_dataframe(self, resolved_input: Path) -> pd.DataFrame:
        suffix = resolved_input.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(resolved_input)
        if suffix in {".tsv", ".txt"}:
            return pd.read_csv(resolved_input, sep="\t")
        if suffix == ".json":
            return pd.read_json(resolved_input)
        if suffix == ".jsonl":
            return pd.read_json(resolved_input, lines=True)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(resolved_input)
        if suffix == ".parquet":
            return pd.read_parquet(resolved_input)
        if suffix == ".feather":
            return pd.read_feather(resolved_input)
        raise ValueError(
            "Unsupported dataset format for translation. Supported: csv, tsv, txt, json, jsonl, xlsx, xls, parquet, feather."
        )

    def _validate_text_columns(
        self,
        dataframe: pd.DataFrame,
        text_columns: list[str],
    ) -> None:
        missing_columns = [column for column in text_columns if column not in dataframe.columns]
        if missing_columns:
            raise ValueError(f"Missing text columns: {missing_columns}")

    async def _translate_batch(
        self,
        client: httpx.AsyncClient,
        rows: pd.DataFrame,
        text_columns: list[str],
        target_language: str,
        model_name: str,
    ) -> dict[int, dict[str, str]]:
        payload_rows = []
        for row_index, row in rows.iterrows():
            payload_rows.append(
                {
                    "row_index": int(row_index),
                    "texts": {
                        column: self._normalize_cell_value(row[column])
                        for column in text_columns
                    },
                }
            )

        schema = self._build_response_schema(text_columns=text_columns)
        instructions = (
            f"Translate the provided text fields into {target_language}. "
            "Preserve meaning, named entities, numbers, negation, quantifiers, temporal cues, and inference-relevant details. "
            "Do not explain. Return only the JSON object required by the schema."
        )

        response = await client.post(
            "/chat/completions",
            json={
                "model": model_name,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "target_language": target_language,
                                "rows": payload_rows,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": schema,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        translated_rows: dict[int, dict[str, str]] = {}
        for item in parsed["items"]:
            translated_rows[int(item["row_index"])] = {
                key: value for key, value in item["translations"].items()
            }
        return translated_rows

    def _build_response_schema(self, text_columns: list[str]) -> dict[str, Any]:
        translation_properties = {
            column: {"type": "string"} for column in text_columns
        }
        return {
            "name": "dataset_translation_batch",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "row_index": {"type": "integer"},
                                "translations": {
                                    "type": "object",
                                    "properties": translation_properties,
                                    "required": text_columns,
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["row_index", "translations"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        }

    def _normalize_cell_value(self, value: Any) -> str:
        if pd.isna(value):
            return ""
        return str(value)

    def _build_pass_through_rows(
        self,
        dataframe: pd.DataFrame,
        text_columns: list[str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row_index, row in dataframe.iterrows():
            item = {"row_index": int(row_index)}
            for column in text_columns:
                item[column] = self._normalize_cell_value(row[column])
            rows.append(item)
        return rows

    def _build_write_request(
        self,
        dataframe: pd.DataFrame,
        request: DatasetTranslateRequest,
        resolved_input: Path,
    ) -> DatasetWriteRequest:
        output = request.output.model_copy(deep=True)
        if not output.path:
            output.path = self._default_output_path(resolved_input, request)
        return DatasetWriteRequest(
            rows=dataframe.where(pd.notnull(dataframe), None).to_dict(orient="records"),
            output=output,
        )

    def _default_output_path(
        self,
        resolved_input: Path,
        request: DatasetTranslateRequest,
    ) -> str:
        if request.output.path:
            return str(Path(request.output.path).expanduser().resolve())
        return str(resolved_input.with_name(f"{resolved_input.stem}.translated.vi.csv"))
