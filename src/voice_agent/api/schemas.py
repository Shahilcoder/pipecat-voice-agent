from typing import Literal

from pydantic import BaseModel, ConfigDict


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    room_name: str
    livekit_url: str
    user_token: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    active_sessions: int
