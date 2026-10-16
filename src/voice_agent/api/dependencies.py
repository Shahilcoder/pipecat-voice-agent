import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from voice_agent.sessions.session_manager import SessionManager

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    request: Request, api_key: Annotated[str | None, Security(api_key_header)]
) -> None:
    expected_key = request.app.state.settings.server.api_key.get_secret_value()
    # secrets.compare_digest <- constant time string comparison
    if api_key is None or not secrets.compare_digest(api_key.encode(), expected_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


SessionManagerDependency = Annotated[SessionManager, Depends(get_session_manager)]
