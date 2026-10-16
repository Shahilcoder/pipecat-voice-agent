from fastapi import APIRouter, Depends, HTTPException, status

from voice_agent.api.dependencies import SessionManagerDependency, require_api_key
from voice_agent.api.schemas import HealthResponse, SessionResponse
from voice_agent.sessions.session_manager import SessionCapacityError

router = APIRouter()


@router.get("/health")
async def health(session_manager: SessionManagerDependency) -> HealthResponse:
    return HealthResponse(active_sessions=session_manager.active_session_count)


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
async def create_session(session_manager: SessionManagerDependency) -> SessionResponse:
    try:
        session = session_manager.start_session()
    except SessionCapacityError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error

    return SessionResponse.model_validate(session)
