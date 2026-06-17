from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import tool
from pydantic import Field
from src.services import DispatchPlanningService
from src.services.dispatch_planning_service import (
    DEFAULT_GENERATION_BATCH_SIZE,
    MAX_PARALLEL_WORKERS,
)


class DispatchPlanningToolProvider:
    def __init__(self, dispatch_planning_service: DispatchPlanningService) -> None:
        self._dispatch_planning_service = dispatch_planning_service

    @tool(
        name="calculate_dispatch_plan",
        description=(
            "Calculate an adaptive sliding-window subagent plan. Call this before "
            "claiming batches, then keep the returned parallel_workers slots full."
        ),
    )
    def calculate_dispatch_plan(
        self,
        samples: Annotated[
            int,
            Field(ge=1, description="Samples assigned to this local generation run."),
        ],
        batch_size: Annotated[
            int,
            Field(ge=1, description="Samples processed by one subagent. Default: 20."),
        ] = DEFAULT_GENERATION_BATCH_SIZE,
        max_parallel_workers: Annotated[
            int,
            Field(
                ge=1,
                le=MAX_PARALLEL_WORKERS,
                description="Maximum concurrent subagents. Hard cap: 10.",
            ),
        ] = MAX_PARALLEL_WORKERS,
    ) -> dict[str, Any]:
        return self._dispatch_planning_service.calculate_dispatch_plan(
            samples=samples,
            batch_size=batch_size,
            max_parallel_workers=max_parallel_workers,
        ).model_dump(mode="json")


def register_dispatch_planning_tools(
    mcp: FastMCP,
) -> DispatchPlanningToolProvider:
    provider = DispatchPlanningToolProvider(DispatchPlanningService())
    mcp.add_tool(provider.calculate_dispatch_plan)
    return provider
