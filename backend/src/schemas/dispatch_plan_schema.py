from typing import Literal

from pydantic import BaseModel, Field


class DispatchPlanRequest(BaseModel):
    samples: int = Field(
        ge=1,
        description="Number of samples assigned to the local generation run.",
    )
    batch_size: int = Field(
        default=20,
        ge=1,
        description="Samples processed by one subagent.",
    )
    max_parallel_workers: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Maximum subagents running concurrently.",
    )


class DispatchPlanResponse(BaseModel):
    samples: int
    batch_size: int
    total_batches: int
    max_parallel_workers: int
    parallel_workers: int
    dispatch_strategy: Literal["sliding_window"] = "sliding_window"
