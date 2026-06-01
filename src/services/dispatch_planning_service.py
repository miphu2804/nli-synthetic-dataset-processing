from math import ceil

from src.schemas import DispatchPlanResponse

DEFAULT_GENERATION_BATCH_SIZE = 20
MAX_PARALLEL_WORKERS = 10


class DispatchPlanningService:
    def calculate_dispatch_plan(
        self,
        samples: int,
        batch_size: int = DEFAULT_GENERATION_BATCH_SIZE,
        max_parallel_workers: int = MAX_PARALLEL_WORKERS,
    ) -> DispatchPlanResponse:
        if samples < 1:
            raise ValueError("samples must be at least 1.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")
        if not 1 <= max_parallel_workers <= MAX_PARALLEL_WORKERS:
            raise ValueError(
                f"max_parallel_workers must be between 1 and {MAX_PARALLEL_WORKERS}."
            )

        total_batches = ceil(samples / batch_size)
        return DispatchPlanResponse(
            samples=samples,
            batch_size=batch_size,
            total_batches=total_batches,
            max_parallel_workers=max_parallel_workers,
            parallel_workers=min(total_batches, max_parallel_workers),
        )
