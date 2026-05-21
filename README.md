<div align="center">
  <img src="docs-site/public/images/logo.svg" width="88" height="88" alt="L.U.N.A." />
  <h1>L.U.N.A.</h1>
  <p><strong>Large Unified Nexus Mind AI</strong></p>
  <p><em>Local-first AI companion - voice, memory, vision, and desktop automation.</em></p>

  <p>
    <a href="https://github.com/Sehastrajit/Luna/stargazers">
      <img src="https://img.shields.io/github/stars/Sehastrajit/Luna?style=for-the-badge&logo=github&color=6d28d9&labelColor=030306" alt="Stars" />
    </a>
    <a href="https://github.com/Sehastrajit/Luna/forks">
      <img src="https://img.shields.io/github/forks/Sehastrajit/Luna?style=for-the-badge&logo=github&color=7c3aed&labelColor=030306" alt="Forks" />
    </a>
    <a href="https://github.com/Sehastrajit/Luna/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/Sehastrajit/Luna?style=for-the-badge&color=8b5cf6&labelColor=030306" alt="License" />
    </a>
    <a href="https://github.com/Sehastrajit/Luna/commits/main">
      <img src="https://img.shields.io/github/last-commit/Sehastrajit/Luna?style=for-the-badge&color=a78bfa&labelColor=030306" alt="Last Commit" />
    </a>
    <a href="https://github.com/Sehastrajit/Luna/issues">
      <img src="https://img.shields.io/github/issues/Sehastrajit/Luna?style=for-the-badge&color=c4b5fd&labelColor=030306" alt="Issues" />
    </a>
  </p>

  <p>
    <a href="https://github.com/Sehastrajit/Luna">
      <img src="https://img.shields.io/badge/View%20on%20GitHub-%23030306?style=for-the-badge&logo=github&logoColor=white" alt="View on GitHub" />
    </a>
  </p>

  <br />

  <img src="https://img.shields.io/badge/Electron-191970?style=flat-square&logo=electron&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi" />
  <img src="https://img.shields.io/badge/TypeScript-007ACC?style=flat-square&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-07405E?style=flat-square&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Three.js-000000?style=flat-square&logo=three.js&logoColor=white" />
</div>

<br />

---

L.U.N.A. is an open-source AI platform that ships as two variants: a **Personal** local-first companion (voice, vision, Spotify, desktop automation) and a **Business** team assistant (multi-user JWT auth, rate limiting, Telegram/Discord/Slack channels). Both support 8 LLM providers: Ollama, NVIDIA NIM, Anthropic, Google, Groq, Cohere, Mistral, and any OpenAI-compatible endpoint.

---

## Table of Contents

- [Variants](#variants)
- [Features](#features)
- [Install â€” one line](#install--one-line)
- [Docker](#docker)
- [Any Model](#any-model)
- [Quick Start (desktop)](#quick-start-desktop)
- [Documentation Site](#documentation-site)
- [Stack](#stack)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Device Support](#device-support)
- [Project Layout](#project-layout)
- [Automated Testing](#automated-testing)
- [Contributing](#contributing)
- [Privacy](#privacy)
- [License](#license)

---

## Variants

| | **Personal** | **Business** |
|---|---|---|
| **Best for** | Individual daily use | Teams & companies |
| **Tone** | Casual companion | Professional |
| **Auth** | None required | Multi-user JWT |
| **Rate limiting** | Off | Sliding-window, configurable |
| **Messaging channels** | â€” | Telegram, Discord, Slack, Webhook |
| **Voice / vision** | âœ“ | â€” |
| **Spotify / app launcher** | âœ“ | â€” |
| **Calendar & web search** | âœ“ | âœ“ |
| **Docker** | `luna docker` | `luna docker:business` |

Switch at any time by changing `luna_variant=personal` or `luna_variant=business` in `.env` and restarting. No data is lost.

---

## Install â€” one line

```bash
git clone https://github.com/Sehastrajit/Luna.git
cd Luna
npm install
npm run luna -- setup
```

The interactive wizard selects your variant (Personal or Business), configures your LLM provider, installs all dependencies, and pulls Ollama models. Luna opens on **http://localhost:8899**.

> Voice, Electron shell, and OS-level automation require the [desktop install](#quick-start-desktop).

---

## Docker

The CLI auto-detects the right compose file from your `.env`:

| Command | When | Compose file |
|---|---|---|
| `luna docker` | auto-detect | picks one of the below |
| `luna docker:business` | Business variant | `compose.business.yml` |
| `luna docker:gpu` | NVIDIA GPU | `compose.yml + compose.gpu.yml` |
| `luna docker:cloud` | Cloud LLM (no Ollama) | `compose.cloud.yml` |

```bash
# Personal â€” Ollama CPU (default)
luna docker

# Personal â€” NVIDIA GPU
luna docker:gpu

# Personal â€” cloud LLM (set llm_provider in .env first)
luna docker:cloud

# Business variant
cp .env.business.example .env
# edit jwt_secret, business_name, llm_provider
luna docker:business
```

Data is persisted in named Docker volumes (`luna_data`, `ollama_data`). Upgrading:

```bash
git pull && luna docker
```

---

## Any Model

Luna supports 8 providers natively. Change `llm_provider` in `.env` â€” no code changes, no restart of anything else.

| Provider | `llm_provider` | Key needed |
|---|---|---|
| **Ollama** (local, default) | `ollama` | None |
| **NVIDIA NIM** | `nvidia-nim` | `nvidia_nim_api_key` |
| **Anthropic Claude** | `anthropic` | `anthropic_api_key` |
| **Google Gemini** | `google` | `google_api_key` |
| **Groq** | `groq` | `groq_api_key` |
| **Cohere** | `cohere` | `cohere_api_key` |
| **Mistral AI** | `mistral` | `mistral_api_key` |
| **OpenAI / OpenRouter / LM Studio / llama.cpp** | `openai-compatible` | `openai_api_key` (optional for local) |

**OpenRouter** is the easiest cloud path â€” one key, every major model, pay-as-you-go:

```env
llm_provider=openai-compatible
openai_base_url=https://openrouter.ai/api/v1
openai_api_key=sk-or-...
openai_model=anthropic/claude-opus-4
```

**NVIDIA NIM** uses NVIDIA's OpenAI-compatible `/v1/chat/completions` endpoint:

```env
llm_provider=nvidia-nim
nvidia_nim_base_url=https://integrate.api.nvidia.com/v1
nvidia_nim_api_key=nvapi-...
nvidia_nim_model=meta/llama-3.1-8b-instruct
```

---

## Features

| Capability | Personal | Business |
|---|---|---|
| ðŸŽ™ **Voice** â€” wake-word, push-to-talk, faster-whisper STT, edge-tts / pyttsx3 TTS | âœ“ | â€” |
| ðŸ§  **Memory** â€” persistent facts, personality state, conversation summaries (SQLite + ChromaDB) | âœ“ | âœ“ |
| ðŸ‘ **Vision** â€” screen and camera awareness without storing raw frames | âœ“ | â€” |
| âš¡ **Automation** â€” app launcher, Spotify control, audio device switcher | âœ“ | â€” |
| ðŸ“… **Calendar & Tasks** â€” create, list, update tasks with proactive reminders | âœ“ | âœ“ |
| ðŸ“Š **Dashboard** â€” live news, weather, markets, and maps widget layer | âœ“ | âœ“ |
| ðŸŒ **Web Tools** â€” DuckDuckGo search and page fetch | âœ“ | âœ“ |
| ðŸ§© **Dynamic Widgets** â€” steps, timelines, code blocks, 3D scenes (Three.js) | âœ“ | âœ“ |
| âœˆï¸ **Messaging Channels** â€” Telegram, Discord, Slack, generic webhook | â€” | âœ“ |
| ðŸ” **JWT Auth** â€” multi-user tokens, admin user management API | â€” | âœ“ |
| ðŸš¦ **Rate Limiting** â€” sliding-window per-IP, configurable burst | â€” | âœ“ |
| ðŸ”’ **Private** â€” inference runs locally via Ollama by default, zero telemetry | âœ“ | âœ“ |

---

## Quick Start (desktop)

**Prerequisites:** Node.js 18+, Python 3.10+, [Ollama](https://ollama.com/) installed and running.

### 1 â€” Clone and run the setup wizard

```bash
git clone https://github.com/Sehastrajit/Luna.git
cd Luna
npm install
npm run luna -- setup
```

The wizard selects your variant, configures your LLM provider, installs all Node and Python dependencies, and pulls Ollama models. Takes about 2 minutes on a fast connection.

### 2 â€” Start Luna

```bash
luna dev         # Electron + Vite + FastAPI (full desktop)
# or
luna web         # FastAPI + browser UI, no Electron
# or
luna backend     # FastAPI only (use any HTTP client)
```

Open `http://localhost:5173` in your browser, or use the Electron window.

> **Tip:** Run `luna doctor` if something doesn't start â€” it checks Node, Python, Ollama, and Docker in one shot.

### Desktop installer

Build the Windows installer with:

```powershell
npm run installer
```

The Electron installer uses an assisted NSIS flow. On first launch, Luna opens a setup window before starting the backend so the user can choose **Personal** or **Business**, select the LLM provider, and enter required credentials. The same settings window is available later from the gear button in the Electron title bar or the tray menu.

---

## Documentation Site

The documentation lives in `docs-site/` and runs as a Next.js app.

```bash
npm run docs
```

Open `http://localhost:3000` to browse the docs locally. The docs site includes a light/dark theme toggle in the top bar; your preference is saved in the browser.

Production build:

```bash
npm run docs:build
npm run docs:start
```

---

## CLI Chat

After Luna is running, start an interactive terminal chat:

```bash
luna chat
# or â€” one-shot
luna chat "what time is it?"
```

Inside chat, use `/new` to start a fresh conversation and `/exit` to quit.

---

## Stack

### Frontend

| Layer | Tech |
|---|---|
| Shell | Electron |
| UI Framework | React + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS |
| State | Zustand |
| 3D | Three.js |
| Maps | MapLibre GL |

### Backend

| Layer | Tech |
|---|---|
| API | FastAPI + Uvicorn |
| Database | SQLite |
| Vector store | ChromaDB |
| LLM | Ollama, Anthropic, Google, Groq, Cohere, Mistral, or any OpenAI-compatible endpoint |
| STT | faster-whisper |
| TTS | pyttsx3 |
| HTTP | httpx / requests |

### AI Models

| Purpose | Default |
|---|---|
| Chat | `qwen2.5:7b` via Ollama (configurable) |
| Embeddings | `nomic-embed-text` |
| Vision | `moondream` |

---

## Architecture

Luna has three layers:

1. **Electron** â€” starts the desktop shell, launches the FastAPI backend, and hosts the React renderer.
2. **React** â€” renders chat, voice controls, Luna dashboard, maps, dynamic widgets, and 3D scenes.
3. **FastAPI** â€” owns chat streaming, voice, memory, vision, tool execution, live data, Spotify, scheduling, messaging channels, auth, rate limiting, and all LLM calls.

Chat is streamed over **Server-Sent Events**. A typical stream includes metadata, token chunks, command events, and a `done` event. Commands can open widgets, show maps, trigger Spotify controls, run web searches, generate 3D scenes, or execute desktop automation.

```
User input (browser Â· Electron Â· Telegram Â· Discord Â· Slack Â· webhook)
    â”‚
    â–¼
Variant check (personal | business)
    â”‚
    â–¼
Context assembly (memory + personality + calendar + vision + conversation)
    â”‚
    â–¼
LLM inference  â†â”€â”€â”€â”€â”€â”€ Ollama / NVIDIA NIM / Anthropic / Google / Groq / Cohere / Mistral / OpenAI-compatible
    â”‚
    â–¼
Tool execution (web_search Â· web_fetch Â· Spotify Â· calendar Â· widgets Â· maps)
    â”‚
    â–¼
Memory update  (fact extraction Â· personality update Â· conversation compaction)
    â”‚
    â–¼
Response streamed to UI  (or plain-text reply to channel)
```

Full diagrams: [architecture.svg](architecture.svg) Â· [architecture_ai.svg](architecture_ai.svg)

---

## Configuration

Copy `.env.example` to `.env`. Never commit `.env`.

```env
# Variant
luna_variant=personal          # personal | business

# Identity
user_name=friend
# LLM â€” Ollama (default)
llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b

# LLM â€” Anthropic Claude (recommended for business)
# llm_provider=anthropic
# anthropic_api_key=sk-ant-...
# anthropic_model=claude-sonnet-4-5

# LLM â€” any OpenAI-compatible (OpenRouter, OpenAI, LM Studio, ...)
# llm_provider=openai-compatible
# openai_base_url=https://openrouter.ai/api/v1
# openai_api_key=sk-or-...
# openai_model=anthropic/claude-opus-4

# LLM — NVIDIA NIM
# llm_provider=nvidia-nim
# nvidia_nim_api_key=nvapi-...
# nvidia_nim_model=meta/llama-3.1-8b-instruct

# Business â€” auth & rate limiting
# jwt_secret=change-me
# rate_limit_enabled=true
# rate_limit_per_minute=60

# Messaging channels (business)
# telegram_bot_token=
# discord_bot_token=
# slack_bot_token=

# Workspace integrations (optional OAuth access tokens)
# google_workspace_client_id=
# google_workspace_client_secret=
# google_workspace_refresh_token=
# google_workspace_access_token=
# microsoft_workspace_client_id=
# microsoft_workspace_client_secret=
# microsoft_workspace_tenant_id=common
# microsoft_workspace_refresh_token=
# microsoft_workspace_access_token=

# Optional personal features
the_news_api=
spotify_client_id=
spotify_client_secret=
```

Workspace API routes:

```http
GET  /api/integrations/workspace/status
POST /api/integrations/workspace/google/{service}/{action}
POST /api/integrations/workspace/microsoft/{service}/{action}
```

Supported Google services include Gmail, Calendar, Drive, Docs, Sheets, Slides, Tasks, and People. Microsoft 365 uses Microsoft Graph for Outlook mail/calendar, OneDrive, Excel workbooks, To Do, Teams, and profile data. Routes use the `.env` token by default, can refresh tokens when OAuth client credentials are configured, and also accept `Authorization: Bearer <token>` per request.

Full reference: `docs-site/pages/environment.js` or run `luna setup` for guided configuration.

---

## Device Support

**Desktop (Electron):**

```powershell
npm run dev
```

**Other devices on your LAN (phone, tablet, second computer):**

```env
# .env
host=0.0.0.0
```

```powershell
npm run luna -- web:lan
```

Then open `http://YOUR-LAN-IP:5173` on any device. Use `npm run luna -- dev:lan` only when you also want the Electron shell running on the host computer. Voice, camera, notifications, and OS-level features depend on browser permissions and may be desktop-only.

---

## Project Layout

```
Luna/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ main.py
â”‚   â”œâ”€â”€ middleware/
â”‚   â”‚   â””â”€â”€ rate_limit.py         # sliding-window rate limiter
â”‚   â”œâ”€â”€ processes/
â”‚   â”‚   â”œâ”€â”€ registry.py
â”‚   â”‚   â”œâ”€â”€ calendar_reminders/
â”‚   â”‚   â”œâ”€â”€ memory_maintenance/
â”‚   â”‚   â”œâ”€â”€ proactive_followups/
â”‚   â”‚   â””â”€â”€ voice_runtime/
â”‚   â”œâ”€â”€ routers/
â”‚   â”‚   â”œâ”€â”€ admin.py              # user management, JWT tokens
â”‚   â”‚   â”œâ”€â”€ channels.py           # Telegram / Discord / Slack / webhook
â”‚   â”‚   â”œâ”€â”€ chat.py
â”‚   â”‚   â”œâ”€â”€ luna.py
â”‚   â”‚   â”œâ”€â”€ system.py
â”‚   â”‚   â”œâ”€â”€ vision.py
â”‚   â”‚   â”œâ”€â”€ voice.py
â”‚   â”‚   â””â”€â”€ spotify.py
â”‚   â””â”€â”€ services/
â”‚       â”œâ”€â”€ channel_bridge.py     # channel session & reply routing
â”‚       â”œâ”€â”€ dashboard/
â”‚       â”‚   â”œâ”€â”€ articles.py
â”‚       â”‚   â”œâ”€â”€ markets.py
â”‚       â”‚   â”œâ”€â”€ news.py
â”‚       â”‚   â””â”€â”€ weather.py
â”‚       â”œâ”€â”€ llm.py                # 8-provider LLM client
â”‚       â”œâ”€â”€ memory.py
â”‚       â”œâ”€â”€ personality.py
â”‚       â”œâ”€â”€ scheduler.py
â”‚       â”œâ”€â”€ tool_registry.py
â”‚       â”œâ”€â”€ vision.py
â”‚       â””â”€â”€ web_tools.py
â”œâ”€â”€ electron/
â”‚   â”œâ”€â”€ main.js
â”‚   â””â”€â”€ preload.js
â”œâ”€â”€ frontend/
â”‚   â””â”€â”€ src/
â”‚       â”œâ”€â”€ components/
â”‚       â”‚   â”œâ”€â”€ Dynamic/
â”‚       â”‚   â”‚   â”œâ”€â”€ DynamicWidgetOverlay.tsx
â”‚       â”‚   â”‚   â”œâ”€â”€ GeneratedScene.tsx
â”‚       â”‚   â”‚   â””â”€â”€ ThreeDScene.tsx
â”‚       â”‚   â”œâ”€â”€ Luna/
â”‚       â”‚   â”œâ”€â”€ Map/
â”‚       â”‚   â””â”€â”€ Voice/
â”‚       â”œâ”€â”€ hooks/
â”‚       â”œâ”€â”€ services/
â”‚       â””â”€â”€ store/
â”œâ”€â”€ docs-site/          # Next.js documentation site
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ ARCHITECTURE.md
â”‚   â”œâ”€â”€ PROCESSES.md
â”‚   â”œâ”€â”€ CLI.md
â”‚   â””â”€â”€ VSCODE.md
â”œâ”€â”€ architecture.svg
â”œâ”€â”€ architecture_ai.svg
â””â”€â”€ .env.example
```

---

## Agent Platform

Luna includes a foundation for broader agent workflows:

- **Skills** â€” local skills in `skills/` or `data/workspace/skills/` with `skill.json` and `SKILL.md`
- **Permissions** â€” every tool has a mode: `allow`, `confirm`, or `block`
- **Workspace** â€” agent-created files are sandboxed to `data/workspace/`
- **Audit log** â€” all tool and agent actions written to `data/audit.log`
- **Browser** â€” public page reading over HTTP; optional Playwright for full browser automation
- **Tasks** â€” multi-step tasks can be created, planned, and expanded over time

```
GET  /api/agent/skills
GET  /api/agent/permissions
POST /api/agent/permissions/{tool_name}
GET  /api/agent/workspace
POST /api/agent/workspace/write
GET  /api/agent/tasks
POST /api/agent/tasks
GET  /api/agent/audit
```

---

## Automated Testing

Run the smoke suite before opening a PR:

```powershell
npm run test:smoke
```

This runs backend syntax checks, validates the CLI entrypoint, and executes the separated tool smoke tests under `tests/tools/`. The tool tests cover:

- Spotify command parsing and auth-state readability
- App launcher discovery without opening apps
- Tool registry coverage and risk labels
- CLI syntax checks
- Screen, browser/web, workspace, task/calendar, system, GitHub, skill, and agent-task tool wiring

For only the tool smoke tests:

```powershell
npm run test:tools
```

For frontend changes, also run:

```powershell
npm run build
```

The smoke tests intentionally do not click, type, lock the screen, switch audio devices, launch apps, or start playback. Tests that need persistence use an in-memory database or write a temporary workspace/agent-task record and clean it up.

---

## Contributing

1. Fork the repo and create a branch from `main`.
2. Make your changes. Run `npm run test:smoke` for backend, CLI, and tool wiring checks.
3. Run `npm run build` for frontend changes.
4. Open a pull request with a clear description of what changed and why.

Please avoid non-ASCII characters in backend log messages (Windows `cp1252` compatibility). See the troubleshooting docs for details.

---

## Privacy

- Chat inference runs through local Ollama â€” no tokens leave your machine by default.
- Memory, facts, and personality state are stored in local SQLite and ChromaDB.
- Vision summaries are generated locally.
- External APIs (news, weather, markets, Spotify) are only contacted when those features are configured and used.
- Keep `.env`, `data/`, and generated memory stores out of version control.

---

## License

MIT â€” see [LICENSE](LICENSE).

---

<div align="center">
  <sub>Built by the L.U.N.A. contributors. Open source, always.</sub>
</div>

