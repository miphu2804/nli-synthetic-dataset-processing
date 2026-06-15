from fastapi import APIRouter, HTTPException

from src.schemas import DispatchPlanRequest, DispatchPlanResponse
from src.services import DispatchPlanningService

dispatch_plan_router = APIRouter(prefix="/api/dispatch-plan", tags=["dispatch-plan"])
dispatch_planning_service = DispatchPlanningService()


@dispatch_plan_router.post("/calculate", response_model=DispatchPlanResponse)
async def calculate_dispatch_plan(
    request: DispatchPlanRequest,
) -> DispatchPlanResponse:
    try:
        return dispatch_planning_service.calculate_dispatch_plan(
            samples=request.samples,
            batch_size=request.batch_size,
            max_parallel_workers=request.max_parallel_workers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
