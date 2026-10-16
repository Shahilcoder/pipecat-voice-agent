import uvicorn

from voice_agent.api.app import create_app
from voice_agent.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.server.host, port=settings.server.port)


if __name__ == "__main__":
    run()
