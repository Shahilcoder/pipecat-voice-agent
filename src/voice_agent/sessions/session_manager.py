import asyncio
import uuid
from dataclasses import dataclass

from loguru import logger
from pipecat.runner.livekit import generate_session_tokens

from voice_agent.bot.voice_bot import RoomConnection, VoiceBot
from voice_agent.config import AppSettings


class SessionCapacityError(Exception):
    """Raised when the server is already running the maximum number of sessions."""


@dataclass(frozen=True)
class Session:
    """What a client needs to join a voice session"""

    session_id: str
    room_name: str
    livekit_url: str
    user_token: str


class SessionManager:
    """Starts voice bot sessions and tracks them until they finish."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._running_bots: dict[str, asyncio.Task[None]] = {}

    @property
    def active_session_count(self) -> int:
        return len(self._running_bots)

    def start_session(self) -> Session:
        if self.active_session_count >= self._settings.server.max_concurrent_sessions:
            raise SessionCapacityError("Maximum concurrent sessions reached, try again later")

        session_id = uuid.uuid4().hex
        room_name = f"voice-agent-{session_id}"
        livekit = self._settings.livekit
        bot_token, user_token = generate_session_tokens(
            room_name, session_id, livekit.api_key, livekit.api_secret.get_secret_value()
        )

        bot = VoiceBot(
            self._settings, RoomConnection(url=livekit.url, room_name=room_name, token=bot_token)
        )
        task = asyncio.create_task(bot.run(), name=f"voice-bot-{session_id}")
        task.add_done_callback(lambda finished: self._on_bot_finished(session_id, finished))
        self._running_bots[session_id] = task

        logger.info(f"Started session {session_id} in room {room_name}")
        return Session(
            session_id=session_id,
            room_name=room_name,
            livekit_url=livekit.url,
            user_token=user_token,
        )

    async def shutdown(self) -> None:
        """Cancel every running bot and wait for them to finish."""
        running_tasks = list(self._running_bots.values())
        for task in running_tasks:
            task.cancel()
        await asyncio.gather(*running_tasks, return_exceptions=True)

    def _on_bot_finished(self, session_id: str, task: asyncio.Task[None]) -> None:
        self._running_bots.pop(session_id, None)
        if task.cancelled():
            logger.info(f"Session {session_id} cancelled")
        elif (error := task.exception()) is not None:
            logger.opt(exception=error).error(f"Session {session_id} crashed")
        else:
            logger.info(f"Session {session_id} ended")
