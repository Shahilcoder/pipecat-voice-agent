# Voice Agent Backend — Implementation Guide

A Pipecat voice agent backend: **LiveKit WebRTC** transport, **Azure STT**, **ElevenLabs TTS**, an
**OpenAI-compatible model-garden LLM**, **RTVI** for client events, and a **FastAPI session API**.

Verified against `pipecat-ai` **1.12.0** (released 2026-09-25). Requires Python ≥ 3.11; this guide pins 3.12.

---

## 0. Architecture

```
Client (web/mobile, @pipecat-ai/client-js + @pipecat-ai/livekit-transport)
   │ 1. POST /sessions  (X-API-Key)
   ▼
FastAPI ──► SessionManager ──► mints bot + user LiveKit tokens
   │                     └──► starts VoiceBot as an asyncio task
   │ 2. {session_id, room_name, livekit_url, user_token}
   ▼
Client joins the LiveKit room with user_token ◄──── WebRTC audio + RTVI data channel ────► VoiceBot

VoiceBot pipeline:
  transport.input → AzureSTT → user aggregator (Silero VAD + Smart Turn v3) → LLM (+tools)
                  → ElevenLabsTTS → transport.output → assistant aggregator
```

**Lifecycle**
1. The client sends the RTVI `client-ready` message.
2. Pipecat replies `bot-ready` automatically, and the bot greets the user.
3. The user leaves the room → `on_client_disconnected` → the runner is cancelled → the task ends and is removed from the manager.
4. If the user never joins, the bot cancels itself after `SERVER_BOT_IDLE_TIMEOUT_SECS` (the `PipelineWorker` idle timeout).

**Pipecat 1.x changes that differ from older tutorials.** Don't copy 0.0.x code:

| Old (0.0.x) | Current (1.x) |
|---|---|
| `PipelineTask`, `PipelineRunner` | `PipelineWorker` (`pipecat.pipeline.worker`), `WorkerRunner` (`pipecat.workers.runner`) |
| `OpenAILLMContext` | `LLMContext` + `LLMContextAggregatorPair` |
| `vad_analyzer=` on transport params | `LLMUserAggregatorParams(vad_analyzer=...)` |
| `voice_id=`, `model=`, `params=InputParams(...)` | `Service.Settings(voice=..., model=...)` |
| Manual `RTVIProcessor` + `RTVIObserver`, `RTVIConfig` | RTVI is **on by default** in `PipelineWorker`; use `worker.rtvi` |
| `allow_interruptions=True` | Interruptions are always on |

---

## 1. Project setup (commands)

Run these from the project root (`pipecat-voice-agent/`):

```bash
# Package layout (src/voice_agent), console-script support, Python 3.12
uv init --package --name voice-agent --python 3.12 .

# Runtime dependencies
uv add "pipecat-ai[azure,elevenlabs,livekit,openai]" fastapi "uvicorn[standard]" pydantic-settings tzdata

# Dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff pyright
```

Why these packages:
- **Silero VAD and Smart Turn v3** ship in pipecat core (onnxruntime is a core dependency), so they need no extra.
- **`livekit`** brings `livekit`, `livekit-api` (for token minting) and `pyjwt`.
- **`tzdata`** lets `zoneinfo` work inside slim Docker images, which have no system timezone database.
- **The `runner` extra is not needed.** We have our own FastAPI server and only import the token helpers from `pipecat.runner.livekit`, which depend only on `livekit-api`.

Optional: `uv tool install "pipecat-ai[cli]"` gives you `pipecat init`, which is handy for comparing your code with the official scaffold. We don't use its output.

Delete the generated `src/voice_agent/__init__.py` body (keep the file, make it empty). `uv init` puts a `main()` stub there.

---

## 2. Final folder structure

```
pipecat-voice-agent/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── src/voice_agent/
│   ├── __init__.py
│   ├── main.py                    # console entrypoint → uvicorn
│   ├── config.py                  # typed, validated settings grouped by integration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py                 # create_app() factory + lifespan
│   │   ├── dependencies.py        # API-key auth, SessionManager accessor
│   │   ├── routes.py              # GET /health, POST /sessions
│   │   └── schemas.py             # HTTP response models
│   ├── sessions/
│   │   ├── __init__.py
│   │   └── session_manager.py     # Session, SessionManager, SessionCapacityError
│   └── bot/
│       ├── __init__.py
│       ├── voice_bot.py           # RoomConnection, VoiceBot (pipeline + event handlers)
│       ├── service_factory.py     # VoiceServiceFactory: STT / LLM / TTS
│       ├── model_garden_llm.py    # ModelGardenLLMService (OpenAI-compatible LLM)
│       ├── tools.py               # LLM tools (function calling)
│       └── prompts.py             # system prompt + greeting
└── tests/
    ├── __init__.py
    ├── test_api.py
    └── test_tools.py
```

**Dependency direction** (each layer imports only from the layers to its right):
`api → sessions → bot → config`.

---

## 3. File-by-file

### 3.1 `pyproject.toml` — edit

`uv add` filled in `dependencies`. Add or replace these sections:

---

### 3.2 `.env.example` — new

This is the single source of truth for configuration. Copy it to `.env` and fill it in. Each variable
prefix maps to one settings class in `config.py`.

`.gitignore` must include `.env` and `.venv/`.

---

### 3.3 `src/voice_agent/config.py` — new

**Purpose:** load every setting from the environment once, validate it at startup, and fail fast with a
clear error if anything is missing. Secrets use `SecretStr` so they never appear in logs or reprs.

**Design:**
- One `BaseSettings` subclass per integration, each with its own `env_prefix`. This keeps the standard env names (`LIVEKIT_URL`, …) and groups related values.
- `AppSettings` aggregates the groups.
- `get_settings()` is cached so the app reads the environment only once.

Notes:
- Pydantic merges `model_config` with the parent's, so every group inherits `env_file`.
- Real environment variables override `.env` values. In Docker, everything comes from the environment.

---

### 3.4 `src/voice_agent/bot/prompts.py` — new

**Purpose:** keep conversation copy out of the code so prompt edits don't touch logic.

```python
SYSTEM_PROMPT = (
    "You are a helpful voice assistant. Your replies are converted to speech, so answer in short, "
    "natural sentences and never use emojis, markdown, bullet points, or other formatting that "
    "cannot be spoken. If you need the current date or time, call the get_current_time tool."
)

GREETING_INSTRUCTION = "Greet the user and briefly introduce yourself in one sentence."
```

---

### 3.5 `src/voice_agent/bot/tools.py` — new

**Purpose:** functions the LLM can call. This uses Pipecat's **direct functions** style:
- The function signature and Google-style docstring become the tool schema automatically.
- Passing a function to `LLMContext(tools=[...])` registers it automatically, so `register_function` is not needed.
- The first parameter is always `params: FunctionCallParams`.
- Return the result by awaiting `params.result_callback(...)`.

**To add a tool:** write another `async def` in the same shape and append it to `TOOLS`. For per-tool
options, decorate it with `@tool_options(cancel_on_interruption=False, timeout_secs=30)` from
`pipecat.adapters.schemas.direct_function`.

---

### 3.6 `src/voice_agent/bot/model_garden_llm.py` — new

**Purpose:** the LLM client for your model garden, assumed to expose an **OpenAI-compatible Chat
Completions API** (`base_url` + `api_key` + `model`).

Why subclass `OpenAILLMService`:
- Pipecat follows the same pattern for its own OpenAI-compatible providers (Together, DeepSeek, OpenRouter, …).
- Many OpenAI-compatible servers reject the `"developer"` message role. Setting `supports_developer_role = False` makes Pipecat's adapter convert those messages to `"user"`.
- Our greeting instruction uses the `"developer"` role.

**If the model garden is *not* OpenAI-compatible:** only this file and
`VoiceServiceFactory.create_llm` change. Pipecat has native services for Vertex
(`pipecat.services.google.vertex`), Azure (`pipecat.services.azure.llm`), and others.

**Tool calling** requires the chosen model to support OpenAI-style `tools`. Check this with the model garden.

---

### 3.7 `src/voice_agent/bot/service_factory.py` — new

**Purpose:** build the three AI services from settings. This is the single place that knows vendor
classes and how to configure them. It uses the 1.x `Settings` objects, not the deprecated `voice_id=` /
`model=` arguments.

Notes:
- `ElevenLabsTTSService` uses the WebSocket API, which gives lower latency and word timestamps. The HTTP variant, `ElevenLabsHttpTTSService`, is slower.
- Create the services fresh for each session (the factory is called inside `VoiceBot.run`). Pipecat services are stateful and must not be shared between pipelines.

---

### 3.8 `src/voice_agent/bot/voice_bot.py` — new

**Purpose:** one voice conversation. It connects to a LiveKit room, assembles the pipeline, wires the
RTVI and transport events, and runs until the user leaves or the idle timeout fires.

**Key points:**
- **`RoomConnection`** is an immutable value object holding what the bot needs to join a room.
- **`PipelineWorker` enables RTVI by default.** It prepends an `RTVIProcessor`, adds an `RTVIObserver` (which streams transcripts, bot speaking state, metrics and so on to the client over the LiveKit data channel), and auto-answers `client-ready` with `bot-ready`. We only add a *second* `on_client_ready` handler for the greeting; event handlers stack, so this doesn't replace Pipecat's.
- **Greeting trigger:** start talking on RTVI `on_client_ready`, not on participant join. That way the client UI is guaranteed to be listening.
- **`WorkerRunner(handle_sigint=False)`:** uvicorn owns process signals. Shutdown goes through `SessionManager.shutdown()`.
- **Turn detection:** the defaults (VAD start plus Smart Turn v3 stop) are the recommended setup, so no extra config is needed.

**Optional (not in v1):** speak a filler while a tool runs. Register
`@llm.event_handler("on_function_calls_started")` and queue `TTSSpeakFrame("One moment.")` to the TTS
service. To do this, keep references to `llm` and `tts` in `run()` instead of creating them inline.

---

### 3.9 `src/voice_agent/sessions/session_manager.py` — new

**Purpose:** start sessions (mint tokens, launch the bot) and track running bots so the server can
report its load, enforce a capacity limit, and shut down cleanly.

**Key points:**
- `generate_session_tokens` (from Pipecat) returns `(bot_token, user_token)`. The participant identities are suffixed with the session id so concurrent sessions never collide. The bot token carries the LiveKit *agent* grant.
- No room-creation API call is needed: LiveKit creates the room when the first participant joins.
- A done-callback removes finished bots and logs crashes, so failures are never silently swallowed.
- `start_session` is a plain `def`: it awaits nothing. `asyncio.create_task` uses the running event loop of the calling request.

---

### 3.10 `src/voice_agent/api/schemas.py` — new

**Purpose:** the HTTP response contracts, kept separate from internal domain objects (`Session`) so
the API shape can evolve independently.

---

### 3.11 `src/voice_agent/api/dependencies.py` — new

**Purpose:** FastAPI dependencies for auth and access to app-scoped objects.

**Key points:**
- `APIKeyHeader` makes the key show up in the OpenAPI docs with an **Authorize** button.
- `secrets.compare_digest` gives a constant-time comparison that resists timing attacks. Compare **bytes**, because the `str` form raises `TypeError` on non-ASCII input, which would surface as a 500.

---

### 3.12 `src/voice_agent/api/routes.py` — new

**Purpose:** the HTTP endpoints. They are thin: translate HTTP to domain calls and domain errors to
status codes, with no business logic.

---

### 3.13 `src/voice_agent/api/app.py` — new

**Purpose:** the application factory.
- It configures logging.
- It stores settings on `app.state` immediately, so auth works even before lifespan runs.
- It creates the `SessionManager` in `lifespan` and shuts it down on exit, so all bots are cancelled when the server stops.
- `settings` is optional so the factory also works as `uvicorn --factory voice_agent.api.app:create_app` (dev hot-reload).

---

### 3.14 `src/voice_agent/main.py` — new

**Purpose:** the process entrypoint, used by the `voice-agent` console script and the Docker `CMD`.

---

### 3.15 `src/voice_agent/__init__.py`, `api/__init__.py`, `sessions/__init__.py`, `bot/__init__.py`, `tests/__init__.py` — new/empty

These are empty package markers. Don't re-export anything; explicit imports keep the dependency graph readable.

---

### 3.16 `tests/test_tools.py` — new

`AsyncMock` stands in for `FunctionCallParams`, since the tool only needs `result_callback`.

---

### 3.17 `tests/test_api.py` — new

This tests the HTTP contract without any network access:
- `VoiceBot.run` is replaced with a coroutine that just waits, so nothing connects to LiveKit or the AI vendors.
- Token minting is local JWT signing, so dummy LiveKit credentials work.
- `with TestClient(...)` runs the lifespan, which creates the `SessionManager` and cancels bots on exit.

---

### 3.18 `Dockerfile` — new

This is uv's official multi-stage pattern. Dependencies are cached in their own layer. The final image
contains only the venv, not the uv binary or the source code.

We don't use `dailyco/pipecat-base`: it is built for Pipecat Cloud's `bot.py` contract, and Pipecat
Cloud doesn't document LiveKit support.

### 3.19 `.dockerignore` — new

```
.venv
.env
.git
__pycache__
.pytest_cache
.ruff_cache
tests
```

### 3.20 `docker-compose.yml` — new

```yaml
services:
  voice-agent:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    restart: unless-stopped
```

---

## 4. Build order (each step runnable)

1. **Section 1 commands**, then `pyproject.toml` (3.1), `.env.example` (3.2) and `.env`.
2. **`config.py`.** Check that it loads: `uv run python -c "from voice_agent.config import get_settings; print(get_settings())"`. Secrets print as `**********`.
3. **`prompts.py`, `tools.py`, `test_tools.py`.** Run `uv run pytest tests/test_tools.py`.
4. **`model_garden_llm.py`, `service_factory.py`, `voice_bot.py`.**
5. **`session_manager.py`.**
6. **`api/*`, `main.py`, `test_api.py`.** Run `uv run pytest`.
7. **End to end:** `uv run voice-agent`, then create a session with curl and join the room (README step 6).
8. **Docker:** `docker compose up --build`, then repeat step 7.

## 5. Known limits and when to revisit

- **In-process bots.** Each bot runs Silero VAD and Smart Turn v3 (ONNX) on the server CPU, so expect roughly tens of sessions per container. Set `SERVER_MAX_CONCURRENT_SESSIONS` from a load test. When you need more, run bots in worker processes or a queue.
- **Session state lives in memory.** Running several replicas behind a load balancer works, because each replica tracks its own bots, but `/health` shows per-replica counts only.
- **Conversation testing.** Pipecat ships an eval harness (`pipecat-ai[evals]`, `pipecat eval run scenario.yaml`) for LLM-judged conversation tests. Add it once the prompt stabilizes.
- **Model garden API.** It is assumed to be OpenAI-compatible (3.6). Send a sample curl request if it isn't, and only 3.6 and 3.7 change.
