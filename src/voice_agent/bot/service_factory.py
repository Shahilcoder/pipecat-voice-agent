from pipecat.services.azure.stt import AzureSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from voice_agent.bot.model_garden_llm import ModelGardenLLMService
from voice_agent.bot.prompts import SYSTEM_PROMPT
from voice_agent.config import AppSettings


class VoiceServiceFactory:
    """Creates the speech-to-text, LLM, and text-to-speech services for one voice session."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def create_stt(self) -> AzureSTTService:
        azure_speech = self._settings.azure_speech
        return AzureSTTService(
            api_key=azure_speech.api_key.get_secret_value(),
            region=azure_speech.region,
            settings=AzureSTTService.Settings(language=azure_speech.language),
        )

    def create_llm(self) -> ModelGardenLLMService:
        llm = self._settings.llm
        return ModelGardenLLMService(
            api_key=llm.api_key.get_secret_value(),
            base_url=llm.base_url,
            settings=ModelGardenLLMService.Settings(
                model=llm.model, system_instruction=SYSTEM_PROMPT
            ),
        )

    def create_tts(self) -> ElevenLabsTTSService:
        elevenlabs = self._settings.elevenlabs
        return ElevenLabsTTSService(
            api_key=elevenlabs.api_key.get_secret_value(),
            settings=ElevenLabsTTSService.Settings(
                voice=elevenlabs.voice_id,
                model=elevenlabs.model,
            ),
        )
