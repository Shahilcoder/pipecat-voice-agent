from functools import lru_cache

from pipecat.transcriptions.language import Language
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentSettings(BaseSettings):
    """Base for all settings groups: read from environment variables and the .env(.local) file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ServerSettings(EnvironmentSettings):
    model_config = SettingsConfigDict(env_prefix="SERVER_")

    host: str = "0.0.0.0"
    port: int = 8000
    api_key: SecretStr
    log_level: str = "INFO"
    max_concurrent_sessions: int = Field(default=10, ge=1)
    bot_idle_timeout_secs: float = Field(default=300, gt=0)


class LiveKitSettings(EnvironmentSettings):
    model_config = SettingsConfigDict(env_prefix="LIVEKIT_")

    url: str
    api_key: str
    api_secret: SecretStr


class AzureSpeechSettings(EnvironmentSettings):
    model_config = SettingsConfigDict(env_prefix="AZURE_SPEECH_")

    api_key: SecretStr
    region: str
    language: Language = Language.EN_US  # validated against pipecat's Language enum, e.g. "en-US"


class ElevenLabsSettings(EnvironmentSettings):
    model_config = SettingsConfigDict(env_prefix="ELEVENLABS_")

    api_key: SecretStr
    voice_id: str
    model: str = "eleven_multilingual_v2"


class LLMSettings(EnvironmentSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    base_url: str
    api_key: SecretStr
    model: str


class AppSettings(BaseModel):
    """All configuration the service needs, grouped by integration."""

    server: ServerSettings
    livekit: LiveKitSettings
    azure_speech: AzureSpeechSettings
    elevenlabs: ElevenLabsSettings
    llm: LLMSettings


@lru_cache
def get_settings() -> AppSettings:
    """Load and validate settings once. Raises ValidationError if a required variable is missing."""
    # Required fields are filled from the environment, which static type checkers can't see.
    return AppSettings(
        server=ServerSettings(),  # pyright: ignore[reportCallIssue]
        livekit=LiveKitSettings(),  # pyright: ignore[reportCallIssue]
        azure_speech=AzureSpeechSettings(),  # pyright: ignore[reportCallIssue]
        elevenlabs=ElevenLabsSettings(),  # pyright: ignore[reportCallIssue]
        llm=LLMSettings(),  # pyright: ignore[reportCallIssue]
    )
