<div align="center">
  <img src="docs-site/public/images/logo.svg" width="72" height="72" alt="L.U.N.A." />
  <h1>L.U.N.A.</h1>
  <p><strong>Large Unified Nexus Mind AI</strong></p>
  <p>Local-first AI companion · Voice · Memory · Vision · Automation</p>
  <p>
    <a href="https://github.com/Sehastrajit/Luna">GitHub</a> ·
    <a href="https://www.linkedin.com/in/sehastrajit-s/">LinkedIn</a>
  </p>
</div>

---

L.U.N.A. is a local-first desktop and web AI companion built with Electron, React, FastAPI, and pluggable LLM providers. Core chat, memory, voice, vision, widgets, and automation run on your machine through Ollama. Cloud APIs are optional and only used for configured features such as live news, market data, Spotify, and map tiles.

**Architecture diagrams:**

- [System architecture](architecture.svg)
- [AI inference and tool flow](architecture_ai.svg)

## What Luna Can Do

- Stream chat responses through local Ollama or an OpenAI-compatible model endpoint.
- Listen for wake words and accept push-to-talk voice input.
- Speak responses with local TTS.
- Remember user facts, conversation summaries, and personality preferences.
- Use the camera/screen vision pipeline to build temporal visual context.
- Search the web and fetch pages when the model asks for live information.
- Open dynamic widgets while explaining topics, including tabs, comparisons, step flows, and generated 3D scenes.
- Show a L.U.N.A.-style dashboard for news, weather, markets, music, system state, and map context.
- Control Spotify playback and queues when configured.
- Run scheduler, calendar, task, and proactive follow-up flows.
- Launch apps, browse, show maps, and execute approved desktop actions through backend tools.

## Stack

Frontend:

- Electron shell for desktop
- Browser access for phones, tablets, and other computers on your network
- React + Vite
- TypeScript
- Tailwind CSS
- Zustand
- Three.js
- MapLibre GL

Backend:

- FastAPI
- Uvicorn
- SQLite
- ChromaDB
- Pluggable LLM provider: Ollama or OpenAI-compatible chat completions
- faster-whisper / local STT integrations
- pyttsx3 / local TTS integrations
- httpx / requests for external APIs

AI models:

- Chat model through local Ollama by default
- OpenAI-compatible chat completions for cloud or self-hosted model servers
- `nomic-embed-text` or OpenAI-compatible embeddings for memory embeddings
- `moondream` for lightweight vision descriptions

## High-Level Architecture

Luna has three main layers:

1. Electron starts the desktop shell, launches the backend, and hosts the React renderer.
2. React renders chat, voice controls, Luna dashboard widgets, maps, dynamic widgets, and generated 3D scenes.
3. FastAPI owns chat streaming, voice, memory, vision, tool execution, live data feeds, Spotify, scheduling, and LLM calls.

The backend streams chat through Server-Sent Events. A typical stream includes metadata, token chunks, command events, optional confirmation events, and a final done event. Commands can open widgets, maps, Spotify controls, browser actions, web searches, generated scenes, or desktop automation.

## AI Flow

The main chat route is `/api/chat/stream`.

For each user message, Luna:

1. Checks fast-path intents for actions that should not require a full LLM call.
2. Builds context from memory, personality, current activity, live dashboard state, vision summaries, calendar/task state, and recent conversation.
3. Calls the configured LLM provider with an expanded context window.
4. Streams the answer to the UI.
5. Parses structured tool calls and bracket commands.
6. Executes safe tools such as web search, dynamic widget display, map display, Spotify control, calendar/task actions, or generated 3D scene creation.
7. Runs background memory extraction and summary updates.

Current LLM defaults documented in the diagrams:

- `num_ctx`: 8192
- `num_predict`: 1024

## Dynamic Widgets and 3D Scenes

The dynamic widget layer lets Luna show visual explanations while it talks. The model can request widgets through structured tool calls or bracket tags.

Supported widget styles include:

- Steps
- Lists
- Comparisons
- Tabs
- Code blocks
- Data cards
- Timelines
- Generated 3D scenes

Generated scenes use:

- Backend endpoint: `/api/system/scene`
- Frontend renderer: `GeneratedScene`
- Runtime: Three.js

For example, when asked "how GPUs work visually", Luna can open an interactive 3D visualization instead of only returning a web search result.

## Vision System

The vision route receives frames, sends them to a local vision model, and stores compact observations. Luna does not need to paste every frame into the prompt. Instead, it keeps:

- Recent observations
- A rolling session summary
- Important detected changes
- Current visual context for chat

This gives the assistant awareness of what is happening on screen or camera without flooding the LLM context.

## Live Data

Luna widgets can load live data from configured services:

- News: TheNewsAPI when configured, RSS fallback when needed
- Weather: Open-Meteo by default, no API key required
- Markets: Yahoo Finance and CoinGecko paths, with Alpha Vantage support where configured
- Web search: DuckDuckGo HTML search
- Maps: MapLibre-compatible map tiles and geolocation
- Music: Spotify API when configured

The UI should render provider names only when useful to debug. User-facing widgets should focus on the data itself.

## Configuration

Create or update `.env` in the project root. Do not commit secrets.

Common keys:

```env
user_name=friend
luna_api_key=
llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qcwind/qwen3-8b-instruct-Q4-K-M:latest
the_news_api=...
alpha_vantage=...
open_weather=...
```

Notes:

- Copy `.env.example` to `.env` before running locally.
- Keep `luna_api_key` empty for local-only development, or set a strong random value before exposing the app to other devices.
- Set `llm_provider=ollama` for local Ollama.
- Set `llm_provider=openai-compatible`, `openai_base_url`, `openai_api_key`, and `openai_model` for cloud APIs or self-hosted OpenAI-compatible servers.
- Set `embedding_provider=openai-compatible` only if your configured API supports `/embeddings`; otherwise leave embeddings on Ollama.
- `the_news_api` is used for news when available.
- `alpha_vantage` can be used for market data paths that support it.
- Weather uses Open-Meteo by default and does not require an API key.
- `open_weather` may exist for older flows but should not be required for the current Luna weather widget.

## Device Support

L.U.N.A. can run as a desktop app or as a browser-accessible web app.

Desktop:

```powershell
npm run dev
```

Other devices on your network:

```powershell
# .env
host=0.0.0.0
luna_api_key=replace-with-a-strong-random-key

# start Vite on your LAN
npm run dev:lan
```

Then open `http://YOUR-COMPUTER-LAN-IP:5173` on a phone, tablet, or another computer and enter the same `luna_api_key` when prompted. Voice, camera, notifications, app launching, audio switching, and other OS-level features depend on browser/device permissions and may be desktop-only.

## Development

Install dependencies:

```powershell
npm install
cd frontend
npm install
```

Install Python dependencies according to the backend requirements used by your checkout.

Start Luna:

```powershell
npm run dev
```

If the backend port is already in use, stop the older Luna backend process or change the configured port. The common bind error is:

```text
[Errno 10048] only one usage of each socket address is normally permitted
```

Run backend syntax checks:

```powershell
python -m py_compile backend\routers\chat.py backend\routers\system.py backend\routers\luna.py backend\services\web_tools.py backend\services\vision.py
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## Project Layout

```text
Luna/
  backend/
    main.py
    processes/
      registry.py
      calendar_reminders/
      memory_maintenance/
      proactive_followups/
      voice_runtime/
    routers/
      chat.py
      luna.py
      system.py
      vision.py
      voice.py
      spotify.py
    services/
      dashboard/
        articles.py
        markets.py
        news.py
        weather.py
      memory.py
      personality.py
      scheduler.py
      tool_registry.py
      vision.py
      web_tools.py
  electron/
    main.js
    preload.js
  frontend/
    src/
      components/
        Dynamic/
          DynamicWidgetOverlay.tsx
          GeneratedScene.tsx
          ThreeDScene.tsx
        Luna/
        Map/
        Voice/
      hooks/
      services/
      store/
  docs/
    ARCHITECTURE.md
  architecture.svg
  architecture_ai.svg
  README.md
```

For contributor boundaries and module ownership guidance, see `docs/ARCHITECTURE.md`.
For background/runtime process ownership, see `docs/PROCESSES.md`.
For CLI usage, see `docs/CLI.md`.
For VS Code setup, see `docs/VSCODE.md`.

## Command and Tool Model

Luna supports two command styles:

- Structured JSON tool calls such as `web_search`, `web_fetch`, and UI actions.
- Bracket command tags such as `[WIDGET:...]`, `[WEB_SEARCH:...]`, `[MAP:...]`, `[SPOTIFY:...]`, and related UI commands.

The backend strips command tags from spoken/displayed answer text after converting them into executable command events.

## Agent Platform Layer

Luna includes an OpenClaw-style foundation for broader agent workflows:

- Skills: local skills live in `skills/` or `data/workspace/skills/` with `skill.json` and `SKILL.md`.
- Permissions: every registered tool has a mode of `allow`, `confirm`, or `block`.
- Workspace: agent-created files are restricted to `data/workspace`.
- Audit log: tool and agent actions are appended to `data/audit.log`.
- Browser layer: public page reading works through HTTP now, with optional Playwright support for fuller browser automation.
- Agent tasks: multi-step tasks can be created, planned, listed, and expanded over time.

Main API routes:

```text
GET  /api/agent/skills
GET  /api/agent/permissions
POST /api/agent/permissions/{tool_name}
GET  /api/agent/workspace
GET  /api/agent/workspace/read?path=...
POST /api/agent/workspace/write
GET  /api/agent/browser/status
POST /api/agent/browser/open
POST /api/agent/browser/read
GET  /api/agent/tasks
POST /api/agent/tasks
GET  /api/agent/audit
```

The frontend has an Agent page for reviewing installed skills, permissions, workspace files, browser status, tasks, and the audit stream.

## Privacy

Luna is designed to keep core assistant behavior local:

- Chat inference runs through local Ollama.
- Memory is stored locally in SQLite and ChromaDB.
- Vision summaries are generated locally when using local vision models.
- External services are contacted only for features that need live outside data.

Keep `.env`, local databases, logs, and generated memory stores out of version control.

## Troubleshooting

Voice says "off":

- Confirm microphone permission.
- Confirm the voice route is running.
- Check wake word logs for "Microphone opened OK".

Backend exits with port bind error:

- Another process is already listening on the configured port.
- Stop the older backend/Electron process or change the port.

UI widgets show no data:

- Check the browser console and backend logs.
- Verify the Luna API route returns JSON.
- Confirm `.env` keys exist for optional providers.
- Remember weather should work through Open-Meteo without a key.

Unicode encode error on Windows:

- Replace non-ASCII console log characters with ASCII text, or run Python with UTF-8 output enabled.
- The known symptom is `UnicodeEncodeError` from `cp1252` while printing arrows or box characters.

Dynamic visual explanations only search the web:

- Confirm the model prompt includes widget guidance.
- Confirm `DynamicWidgetOverlay` is mounted.
- Confirm command parsing handles `[WIDGET:...]` and JSON tool calls.
- Confirm `/api/system/scene` works for generated 3D scene requests.
