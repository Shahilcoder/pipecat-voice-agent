import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from voice_agent.api.routes import router
from voice_agent.config import AppSettings, get_settings
from voice_agent.sessions.session_manager import SessionManager


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.server.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        session_manager = SessionManager(settings)
        app.state.session_manager = session_manager
        # The function stops here, now session manager is available
        # via app state, and the app is running and handling requests.
        yield
        # It's done, so shut down the session manager
        await session_manager.shutdown()

    # IMPORTANT: The function defined above is in fact USED here.
    app = FastAPI(title="Voice Agent", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(router)
    return app
