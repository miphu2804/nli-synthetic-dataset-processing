from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import tool
from pydantic import Field
from src.providers.base import ToolProvider
from src.services.base_run_service import DEFAULT_BATCH_SIZE
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dataset_writer_service import DatasetWriterService
from src.services.generation_run_service import GenerationRunService
from src.services.progress_tracking_service import ProgressTrackingService


class GenerationToolProvider(ToolProvider):
    def __init__(self, generation_run_service: GenerationRunService) -> None:
        self._generation_run_service = generation_run_service

    @tool(
        name="start_generation_run",
        description=(
            "Create one local generation run for a zero-based dataset slice. "
            "Call once before claiming batches."
        ),
    )
    def start_generation_run(
        self,
        input_path: Annotated[
            str,
            Field(description="Input CSV or parquet path inside the server container."),
        ],
        output_path: Annotated[
            str | None,
            Field(
                description="Final CSV path inside the server container, such as /data/generated/result.csv."
            ),
        ] = None,
        from_sample: Annotated[
            int,
            Field(
                ge=1,
                description="One-based first sample number assigned to this run.",
            ),
        ] = 1,
        to_sample: Annotated[
            int | None,
            Field(
                ge=1,
                description="One-based last sample number assigned to this run, inclusive.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            Field(ge=1, description="Rows returned by each claim. Default: 20."),
        ] = DEFAULT_BATCH_SIZE,
        agent_id: Annotated[
            str,
            Field(description="Progress writer identifier. Use main for normal runs."),
        ] = "main",
    ) -> dict[str, Any]:
        row_offset, row_limit = self.sample_range_to_offset_limit(
            from_sample=from_sample,
            to_sample=to_sample,
        )
        return self._generation_run_service.start_generation_run(
            input_path=input_path,
            output_path=output_path,
            row_offset=row_offset,
            row_limit=row_limit,
            batch_size=batch_size,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="claim_next_batch",
        description=(
            "Claim the next local batch. The main agent calls this sequentially before "
            "delegating text transformation to stateless workers."
        ),
    )
    def claim_next_batch(self, run_id: str, agent_id: str) -> dict[str, Any]:
        return self._generation_run_service.claim_next_batch(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="submit_batch_result",
        description=(
            "Submit one validated claimed batch. The main agent is the only caller; "
            "subagents return JSON and never mutate progress."
        ),
    )
    def submit_batch_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        rows: list[dict[str, Any]],
        skipped_rows: list[dict[str, Any]] | None = None,
        batch_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._generation_run_service.submit_batch_result(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            rows=rows,
            skipped_rows=skipped_rows,
            batch_stats=batch_stats,
        ).model_dump(mode="json")

    @tool(
        name="get_run_progress",
        description="Inspect progress for an active local generation run.",
    )
    def get_run_progress(self, run_id: str) -> dict[str, Any]:
        return self._generation_run_service.get_run_progress(run_id).model_dump(
            mode="json"
        )

    @tool(
        name="finalize_generation_run",
        description=(
            "Merge output, verify local progress and row count, then delete successful "
            "local run state and batch outputs. Failed verification keeps them for debugging."
        ),
    )
    def finalize_generation_run(
        self,
        run_id: str,
        agent_id: str = "aggregator",
    ) -> dict[str, Any]:
        return self._generation_run_service.finalize_generation_run(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="verify_progress_log",
        description="Verify the integrity of a generation run progress log.",
    )
    def verify_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return self._generation_run_service.verify_progress_log(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="release_batch_claim",
        description="Release an active local claim so the main agent can retry it.",
    )
    def release_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self._generation_run_service.release_batch_claim(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            reason=reason,
        ).model_dump(mode="json")

    @tool(
        name="list_generation_runs",
        description="List unfinished generation runs in the local pipeline directory.",
    )
    def list_generation_runs(self) -> dict[str, Any]:
        return self._generation_run_service.list_generation_runs().model_dump(
            mode="json"
        )


def register_generation_tools(
    mcp: FastMCP,
    pipeline_dir: Path | None = None,
) -> GenerationToolProvider:
    generation_run_service = GenerationRunService(
        dataset_reader_service=DatasetReaderService(),
        dataset_writer_service=DatasetWriterService(),
        progress_tracking_service=ProgressTrackingService(pipeline_dir=pipeline_dir),
    )
    provider = GenerationToolProvider(generation_run_service)
    provider.register(mcp)
    return provider
