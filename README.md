1. **Setup:** `uv sync`, then `cp .env.example .env` and fill it in.
2. **Run (dev, hot reload):**
   `uv run uvicorn voice_agent.api.app:create_app --factory --reload`
3. **Run (prod-like):** `uv run voice-agent`, or `docker compose up --build`.
4. **Checks:** `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest`.
5. **Client integration:**
   - `POST /sessions` with the `X-API-Key` header.
   - Connect a Pipecat client (`@pipecat-ai/client-js` + `@pipecat-ai/livekit-transport`) using `livekit_url` and `user_token`.
   - The client SDK sends `client-ready` automatically. The bot then answers `bot-ready` and greets the user.
6. **Smoke test without a frontend:** create a session with curl, then open the
   [LiveKit Meet](https://meet.livekit.io) custom-server tab with `livekit_url` and `user_token`. You'll
   hear the bot, but there's no RTVI client to send `client-ready`, so it won't greet first. It still
   answers when you speak.
