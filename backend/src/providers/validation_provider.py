from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import tool
from pydantic import Field
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dispatch_planning_service import DEFAULT_GENERATION_BATCH_SIZE
from src.services.progress_tracking_service import ProgressTrackingService
from src.services.validation_run_service import ValidationRunService


class ValidationToolProvider:
    def __init__(self, validation_run_service: ValidationRunService) -> None:
        self._validation_run_service = validation_run_service

    @tool(
        name="start_validation_run",
        description=(
            "Create one local validation run over generated NLI rows. "
            "Call once before claiming masked validation batches."
        ),
    )
    def start_validation_run(
        self,
        input_path: Annotated[
            str,
            Field(
                description=(
                    "Path to the generated CSV or Parquet file inside the server container. "
                    "Must contain a 'label' column with the ground-truth labels — "
                    "do NOT pass a pre-masked file (masked_label only). "
                    "Labels are masked internally before being returned to validators."
                )
            ),
        ],
        output_dir: Annotated[
            str | None,
            Field(description="Directory for the final validation_results.csv output."),
        ] = None,
        from_sample: Annotated[
            int,
            Field(
                ge=1,
                description="One-based first generated sample number assigned to this run.",
            ),
        ] = 1,
        to_sample: Annotated[
            int | None,
            Field(
                ge=1,
                description="One-based last generated sample number assigned to this run, inclusive.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            Field(ge=1, description="Rows returned by each claim. Default: 20."),
        ] = DEFAULT_GENERATION_BATCH_SIZE,
        agent_id: Annotated[
            str,
            Field(description="Progress writer identifier. Use main for normal runs."),
        ] = "main",
    ) -> dict[str, Any]:
        row_offset, row_limit = self._sample_range_to_offset_limit(
            from_sample=from_sample,
            to_sample=to_sample,
        )
        return self._validation_run_service.start_validation_run(
            input_path=input_path,
            output_dir=output_dir,
            row_offset=row_offset,
            row_limit=row_limit,
            batch_size=batch_size,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @staticmethod
    def _sample_range_to_offset_limit(
        from_sample: int,
        to_sample: int | None,
    ) -> tuple[int, int | None]:
        if to_sample is not None and to_sample < from_sample:
            raise ValueError("to_sample must be greater than or equal to from_sample.")
        row_offset = from_sample - 1
        row_limit = None if to_sample is None else to_sample - from_sample + 1
        return row_offset, row_limit

    @tool(
        name="claim_next_validation_batch",
        description=(
            "Claim the next validation batch with labels masked. The returned rows "
            "include premise, hypothesis, source_uid and masked_label only."
        ),
    )
    def claim_next_validation_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        return self._validation_run_service.claim_next_validation_batch(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="submit_validation_result",
        description=(
            "Submit validator verdicts for one claimed masked batch. The runtime "
            "compares predicted_label to the hidden source label."
        ),
    )
    def submit_validation_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        verdicts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._validation_run_service.submit_validation_result(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            verdicts=verdicts,
        ).model_dump(mode="json")

    @tool(
        name="get_validation_progress",
        description="Inspect progress for an active local validation run.",
    )
    def get_validation_progress(self, run_id: str) -> dict[str, Any]:
        return self._validation_run_service.get_validation_progress(run_id).model_dump(
            mode="json"
        )

    @tool(
        name="release_validation_batch_claim",
        description="Release an active local validation claim so it can be retried.",
    )
    def release_validation_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self._validation_run_service.release_validation_batch_claim(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            reason=reason,
        ).model_dump(mode="json")

    @tool(
        name="finalize_validation_run",
        description=(
            "Merge validation batch outputs into validation_results.csv, verify "
            "progress, then cleanup local run state and batch outputs."
        ),
    )
    def finalize_validation_run(
        self,
        run_id: str,
        agent_id: str = "validator-aggregator",
    ) -> dict[str, Any]:
        return self._validation_run_service.finalize_validation_run(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="verify_validation_progress_log",
        description="Verify the integrity of a validation run progress log.",
    )
    def verify_validation_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return self._validation_run_service.verify_validation_progress_log(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="list_validation_runs",
        description="List unfinished validation runs in the local pipeline directory.",
    )
    def list_validation_runs(self) -> dict[str, Any]:
        return self._validation_run_service.list_validation_runs().model_dump(
            mode="json"
        )


def register_validation_tools(
    mcp: FastMCP,
    pipeline_dir: Path | None = None,
) -> ValidationToolProvider:
    validation_run_service = ValidationRunService(
        dataset_reader_service=DatasetReaderService(),
        progress_tracking_service=ProgressTrackingService(
            pipeline_dir=pipeline_dir or Path(".pipeline/validation")
        ),
    )
    provider = ValidationToolProvider(validation_run_service)
    mcp.add_tool(provider.start_validation_run)
    mcp.add_tool(provider.claim_next_validation_batch)
    mcp.add_tool(provider.submit_validation_result)
    mcp.add_tool(provider.get_validation_progress)
    mcp.add_tool(provider.release_validation_batch_claim)
    mcp.add_tool(provider.finalize_validation_run)
    mcp.add_tool(provider.verify_validation_progress_log)
    mcp.add_tool(provider.list_validation_runs)
    return provider
