The guide has a short section on each step, with code, for all 21 files. It's arranged as setup commands, folder structure, file-by-file code, the order
  to build in (with a check after each step), and known limits.

  Things that will catch you out if you've used older Pipecat (0.0.x):
  - Renamed classes: PipelineTask is now PipelineWorker, PipelineRunner is now WorkerRunner, and OpenAILLMContext is replaced by LLMContext.
  - Voice detection setup: voice activity detection now goes on the user aggregator, not the transport.
  - Service options: STT, LLM and TTS options go in Service.Settings(...). The old voice_id= and model= arguments are deprecated.
  - RTVI is on by default, so you don't write it by hand. The guide only adds an on_client_ready handler that triggers the greeting.
    
  Decisions to know about:      
  - Model garden: It is assumed it accepts OpenAI-style requests (base URL, API key, model name). ModelGardenLLMService sets supports_developer_role = False
    because many compatible servers reject the "developer" message role. If your endpoint isn't OpenAI-compatible, send me an example curl request; only
    sections 3.6 and 3.7 change.
  - Tool calling only works if your model supports OpenAI-style tools. Worth checking with whoever runs the model garden.
  - Docker uses uv's standard two-stage build rather than dailyco/pipecat-base, which is built for Pipecat Cloud. Pipecat Cloud doesn't document LiveKit
    support.
  - Capacity: each bot runs voice and turn detection on the server's CPU, all in one process, so expect roughly tens of sessions per container.
    SERVER_MAX_CONCURRENT_SESSIONS returns a 503 when the server is full; set it from a load test.
