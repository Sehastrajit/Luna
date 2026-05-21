<div align="center">
  <img src="docs-site/public/images/logo.svg" width="88" height="88" alt="L.U.N.A." />
  <h1>L.U.N.A.</h1>
  <p><strong>Large Unified Nexus Mind AI</strong></p>
  <p><em>Local-first AI companion - voice, memory, vision, and desktop automation.</em></p>

  <p>
    <a href="https://github.com/luna-ai-project/Luna/stargazers">
      <img src="https://img.shields.io/github/stars/luna-ai-project/Luna?style=for-the-badge&logo=github&color=6d28d9&labelColor=030306" alt="Stars" />
    </a>
    <a href="https://github.com/luna-ai-project/Luna/forks">
      <img src="https://img.shields.io/github/forks/luna-ai-project/Luna?style=for-the-badge&logo=github&color=7c3aed&labelColor=030306" alt="Forks" />
    </a>
    <a href="https://github.com/luna-ai-project/Luna/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/luna-ai-project/Luna?style=for-the-badge&color=8b5cf6&labelColor=030306" alt="License" />
    </a>
    <a href="https://github.com/luna-ai-project/Luna/commits/main">
      <img src="https://img.shields.io/github/last-commit/luna-ai-project/Luna?style=for-the-badge&color=a78bfa&labelColor=030306" alt="Last Commit" />
    </a>
    <a href="https://github.com/luna-ai-project/Luna/issues">
      <img src="https://img.shields.io/github/issues/luna-ai-project/Luna?style=for-the-badge&color=c4b5fd&labelColor=030306" alt="Issues" />
    </a>
  </p>

  <p>
    <a href="https://github.com/luna-ai-project/Luna">
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

L.U.N.A. is an open-source, local-first AI companion. Chat, memory, voice, vision, and automation can run locally through Ollama, or through an opt-in OpenAI-compatible cloud/self-hosted provider. The browser UI works on desktop, phone, tablet, and other computers on your LAN.

---

## Table of Contents

- [Features](#features)
- [Install — one line](#install--one-line)
- [Docker](#docker)
- [Any Model](#any-model)
- [Quick Start (desktop)](#quick-start-desktop)
- [Documentation Site](#documentation-site)
- [Stack](#stack)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Device Support](#device-support)
- [Project Layout](#project-layout)
- [Contributing](#contributing)
- [Privacy](#privacy)
- [License](#license)

---

## Install — one line

```bash
curl -fsSL https://raw.githubusercontent.com/luna-ai-project/Luna/main/install.sh | bash
```

The script checks for Docker, clones the repo, copies `.env.example → .env`, asks CPU / GPU / cloud, and runs `docker compose up`. Luna opens on **http://localhost:8899**.

> Voice, Electron shell, and OS-level automation require the [desktop install](#quick-start-desktop).

---

## Docker

Three compose files cover every scenario:

| File | Use case | Command |
|---|---|---|
| `compose.yml` | Local Ollama (CPU) | `docker compose up -d` |
| `compose.yml` + `compose.gpu.yml` | Local Ollama + NVIDIA GPU | `docker compose -f compose.yml -f compose.gpu.yml up -d` |
| `compose.cloud.yml` | Cloud API (no Ollama) | `docker compose -f compose.cloud.yml up -d` |

**Manual steps:**

```bash
git clone https://github.com/luna-ai-project/Luna.git && cd Luna
cp .env.example .env        # edit model / API keys
docker compose up -d        # CPU local
# or
docker compose -f compose.yml -f compose.gpu.yml up -d   # GPU
# or
docker compose -f compose.cloud.yml up -d                # cloud key in .env
```

Data is persisted in named Docker volumes (`luna_data`, `ollama_data`). Upgrading is:

```bash
git pull
docker compose up -d --build
```

---

## Any Model

Luna treats every LLM as a drop-in. Set two keys in `.env`:

| Provider | `.env` |
|---|---|
| **Ollama** (local, default) | `llm_provider=ollama` · `ollama_model=qwen2.5:7b` |
| **OpenAI** | `llm_provider=openai-compatible` · `openai_base_url=https://api.openai.com/v1` · `openai_api_key=sk-…` · `openai_model=gpt-4o` |
| **Groq** (fast inference) | `openai_base_url=https://api.groq.com/openai/v1` · `openai_model=llama-3.3-70b-versatile` |
| **Anthropic Claude** (via OpenRouter) | `openai_base_url=https://openrouter.ai/api/v1` · `openai_model=anthropic/claude-opus-4` |
| **Google Gemini** (via OpenRouter) | `openai_base_url=https://openrouter.ai/api/v1` · `openai_model=google/gemini-2.5-pro` |
| **LM Studio / Jan.ai** | `openai_base_url=http://localhost:1234/v1` · `openai_api_key=lm-studio` |
| **llama.cpp server** | `openai_base_url=http://localhost:8080/v1` |

**OpenRouter** (`openrouter.ai`) is the easiest cloud path - one API key, every major model, pay-as-you-go.

---

## Features

| Capability | Description |
|---|---|
| 🎙 **Voice** | Wake-word detection and push-to-talk. Local STT with faster-whisper, local TTS with pyttsx3. |
| 🧠 **Memory** | Persistent fact storage, personality state, and conversation summaries in SQLite + ChromaDB. |
| 👁 **Vision** | Screen and camera awareness. Temporal visual context without storing raw frames. |
| ⚡ **Automation** | Launch apps, control Spotify, manage calendar tasks, and execute approved desktop actions. |
| 📊 **Dashboard** | Live news, weather, markets, and maps in a heads-up display widget layer. |
| 🔒 **Private** | Inference runs locally via Ollama. Zero telemetry. No data leaves unless you opt into cloud features. |
| 🧩 **Dynamic Widgets** | Visual explanations with steps, comparisons, tabs, code blocks, timelines, and live 3D scenes (Three.js). |
| 🌐 **Web Tools** | DuckDuckGo search and page fetch when the model asks for live information. |

---

## Quick Start (desktop)

**Prerequisites:** Node.js 18+, Python 3.10+, [Ollama](https://ollama.com/) installed and running.

### 1 — Clone

```bash
git clone https://github.com/luna-ai-project/Luna.git
cd Luna
```

### 2 — Install dependencies

```bash
npm install
cd frontend && npm install && cd ..
python -m venv .venv
```

```powershell
# Windows
.venv\Scripts\activate
```

```bash
# macOS / Linux
source .venv/bin/activate
```

```bash
pip install -r backend/requirements.txt
```

### 3 — Pull your models

```bash
ollama pull qwen2.5:7b          # or any chat model
ollama pull nomic-embed-text    # for memory embeddings
ollama pull moondream           # optional — for vision
```

### 4 — Configure

```bash
cp .env.example .env
# Edit .env — set ollama_model to match what you pulled
```

### 5 — Run

```bash
npm run dev          # desktop (Electron + Vite + FastAPI)
# or
npm run luna -- web  # browser UI + FastAPI only (no Electron)
```

Open `http://localhost:5173` in your browser, or use the Electron window.

> **Tip:** Run `npm run luna -- doctor` first if something doesn't start — it checks your Node, Python, and Ollama versions in one shot.

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

After Luna is running through Docker or the desktop backend, start an interactive terminal chat:

```bash
npm run chat
# or
npm run luna -- chat
```

Inside chat, use `/new` to start a fresh conversation and `/exit` to quit. One-shot messages also work:

```bash
npm run luna -- chat "summarize today's setup"
```

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
| LLM | Ollama (local) or any OpenAI-compatible endpoint |
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

1. **Electron** — starts the desktop shell, launches the FastAPI backend, and hosts the React renderer.
2. **React** — renders chat, voice controls, Luna dashboard, maps, dynamic widgets, and 3D scenes.
3. **FastAPI** — owns chat streaming, voice, memory, vision, tool execution, live data, Spotify, scheduling, and all LLM calls.

Chat is streamed over **Server-Sent Events**. A typical stream includes metadata, token chunks, command events, and a `done` event. Commands can open widgets, show maps, trigger Spotify controls, run web searches, generate 3D scenes, or execute desktop automation.

```
User input
    │
    ▼
Context assembly (memory + personality + calendar + vision + conversation)
    │
    ▼
LLM inference  ←────── Ollama / OpenAI-compatible
    │
    ▼
Tool execution (web_search · web_fetch · Spotify · calendar · widgets · maps)
    │
    ▼
Memory update  (fact extraction · personality update · conversation compaction)
    │
    ▼
Response streamed to UI
```

Full diagrams: [architecture.svg](architecture.svg) · [architecture_ai.svg](architecture_ai.svg)

---

## Configuration

Copy `.env.example` to `.env`. Never commit `.env`.

```env
# Identity
user_name=friend
luna_api_key=                        # leave empty for local-only dev

# LLM — Ollama (default)
llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b

# LLM — OpenAI-compatible cloud / self-hosted
# llm_provider=openai-compatible
# openai_base_url=https://api.openai.com/v1
# openai_api_key=sk-...
# openai_model=gpt-4o

# Optional cloud features (all opt-in)
the_news_api=
alpha_vantage=
spotify_client_id=
spotify_client_secret=
```

Full reference is in `docs-site/pages/environment.js`.

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
luna_api_key=replace-with-a-strong-random-key
```

```powershell
npm run luna -- web:lan
```

Then open `http://YOUR-LAN-IP:5173` on any device. Use `npm run luna -- dev:lan` only when you also want the Electron shell running on the host computer. Voice, camera, notifications, and OS-level features depend on browser permissions and may be desktop-only.

---

## Project Layout

```
Luna/
├── backend/
│   ├── main.py
│   ├── processes/
│   │   ├── registry.py
│   │   ├── calendar_reminders/
│   │   ├── memory_maintenance/
│   │   ├── proactive_followups/
│   │   └── voice_runtime/
│   ├── routers/
│   │   ├── chat.py
│   │   ├── luna.py
│   │   ├── system.py
│   │   ├── vision.py
│   │   ├── voice.py
│   │   └── spotify.py
│   └── services/
│       ├── dashboard/
│       │   ├── articles.py
│       │   ├── markets.py
│       │   ├── news.py
│       │   └── weather.py
│       ├── memory.py
│       ├── personality.py
│       ├── scheduler.py
│       ├── tool_registry.py
│       ├── vision.py
│       └── web_tools.py
├── electron/
│   ├── main.js
│   └── preload.js
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Dynamic/
│       │   │   ├── DynamicWidgetOverlay.tsx
│       │   │   ├── GeneratedScene.tsx
│       │   │   └── ThreeDScene.tsx
│       │   ├── Luna/
│       │   ├── Map/
│       │   └── Voice/
│       ├── hooks/
│       ├── services/
│       └── store/
├── docs-site/          # Next.js documentation site
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROCESSES.md
│   ├── CLI.md
│   └── VSCODE.md
├── architecture.svg
├── architecture_ai.svg
└── .env.example
```

---

## Agent Platform

Luna includes a foundation for broader agent workflows:

- **Skills** — local skills in `skills/` or `data/workspace/skills/` with `skill.json` and `SKILL.md`
- **Permissions** — every tool has a mode: `allow`, `confirm`, or `block`
- **Workspace** — agent-created files are sandboxed to `data/workspace/`
- **Audit log** — all tool and agent actions written to `data/audit.log`
- **Browser** — public page reading over HTTP; optional Playwright for full browser automation
- **Tasks** — multi-step tasks can be created, planned, and expanded over time

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

## Contributing

1. Fork the repo and create a branch from `main`.
2. Make your changes. Run `npm run luna -- check` to verify the backend compiles.
3. Run `cd frontend && npm run build` to verify no TypeScript errors.
4. Open a pull request with a clear description of what changed and why.

Please avoid non-ASCII characters in backend log messages (Windows `cp1252` compatibility). See the troubleshooting docs for details.

---

## Privacy

- Chat inference runs through local Ollama — no tokens leave your machine by default.
- Memory, facts, and personality state are stored in local SQLite and ChromaDB.
- Vision summaries are generated locally.
- External APIs (news, weather, markets, Spotify) are only contacted when those features are configured and used.
- Keep `.env`, `data/`, and generated memory stores out of version control.

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
  <sub>Built by the L.U.N.A. contributors. Open source, always.</sub>
</div>
