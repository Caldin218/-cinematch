from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.health import HealthResponse, HealthService

router = APIRouter(tags=["health"])


def get_health_service(request: Request) -> HealthService:
    return request.app.state.health_service


@router.get("/health", response_model=HealthResponse)
@router.get("/health/live", response_model=HealthResponse, include_in_schema=False)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse,
            responses={503: {"model": HealthResponse}})
def ready(response: Response,
          service: Annotated[HealthService, Depends(get_health_service)]) -> HealthResponse:
    result = service.readiness()
    response.status_code = 200 if result.status == "ready" else 503
    return result
