import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from voice_agent.api.app import create_app
from voice_agent.bot.voice_bot import VoiceBot
from voice_agent.config import get_settings

API_KEY = "test-api-key"
LIVEKIT_URL = "wss://test.livekit.cloud"

TEST_ENVIRONMENT = {
    "SERVER_API_KEY": API_KEY,
    "SERVER_MAX_CONCURRENT_SESSIONS": "1",
    "LIVEKIT_URL": LIVEKIT_URL,
    "LIVEKIT_API_KEY": "test-livekit-key",
    "LIVEKIT_API_SECRET": "test-livekit-secret-that-is-long-enough",
    "AZURE_SPEECH_API_KEY": "test",
    "AZURE_SPEECH_REGION": "eastus",
    "ELEVENLABS_API_KEY": "test",
    "ELEVENLABS_VOICE_ID": "test",
    "LLM_BASE_URL": "https://llm.test/v1",
    "LLM_API_KEY": "test",
    "LLM_MODEL": "test-model",
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for name, value in TEST_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()

    async def run_until_cancelled(self: VoiceBot) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(VoiceBot, "run", run_until_cancelled)

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "active_sessions": 0}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_create_session_rejects_bad_api_key(client: TestClient, headers: dict) -> None:
    assert client.post("/sessions", headers=headers).status_code == 401


def test_create_session_returns_livekit_credentials(client: TestClient) -> None:
    response = client.post("/sessions", headers={"X-API-Key": API_KEY})
    assert response.status_code == 201
    body = response.json()
    assert body["livekit_url"] == LIVEKIT_URL
    assert body["room_name"].startswith("voice-agent-")
    assert body["user_token"]
    assert client.get("/health").json()["active_sessions"] == 1


def test_create_session_rejects_when_at_capacity(client: TestClient) -> None:
    headers = {"X-API-Key": API_KEY}
    assert client.post("/sessions", headers=headers).status_code == 201
    assert client.post("/sessions", headers=headers).status_code == 503
