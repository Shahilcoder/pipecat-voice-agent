from dataclasses import dataclass

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIProcessor
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.workers.runner import WorkerRunner

from voice_agent.bot.prompts import GREETING_INSTRUCTION
from voice_agent.bot.service_factory import VoiceServiceFactory
from voice_agent.bot.tools import TOOLS
from voice_agent.config import AppSettings


@dataclass(frozen=True)
class RoomConnection:
    """Where the bot connects: LiveKit server URL, room name, and the bot's access token."""

    url: str
    room_name: str
    token: str


class VoiceBot:
    """Runs one voice conversation in a LiveKit room until the user leaves or it goes idle."""

    def __init__(self, settings: AppSettings, room: RoomConnection) -> None:
        self._settings = settings
        self._room = room
        self._service_factory = VoiceServiceFactory(settings)

    async def run(self) -> None:
        transport = self._create_transport()
        context = LLMContext(tools=TOOLS)  # pyright: ignore[reportArgumentType]
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
        )

        pipeline = Pipeline(
            [
                transport.input(),
                self._service_factory.create_stt(),
                user_aggregator,
                self._service_factory.create_llm(),
                self._service_factory.create_tts(),
                transport.output(),
                assistant_aggregator,
            ]
        )

        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
            idle_timeout_secs=self._settings.server.bot_idle_timeout_secs,
            processor_unusable_policy=ProcessorUnusablePolicy.END,
        )
        runner = WorkerRunner(handle_sigint=False)

        self._register_event_handlers(transport, worker, runner, context)
        await runner.add_workers(worker)
        await runner.run()

    def _create_transport(self) -> LiveKitTransport:
        return LiveKitTransport(
            url=self._room.url,
            token=self._room.token,
            room_name=self._room.room_name,
            params=LiveKitParams(audio_in_enabled=True, audio_out_enabled=True),
        )

    def _register_event_handlers(
        self,
        transport: LiveKitTransport,
        worker: PipelineWorker,
        runner: WorkerRunner,
        context: LLMContext,
    ) -> None:
        room_name = self._room.room_name

        @worker.rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi: RTVIProcessor) -> None:
            logger.info(f"Client ready in room {room_name}; greeting user")
            context.add_message({"role": "developer", "content": GREETING_INSTRUCTION})

            await worker.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport: LiveKitTransport, client: dict) -> None:
            logger.info(f"Client left room {room_name}; ending session")
            await runner.cancel()
