import DocsLayout from '../components/DocsLayout';
import { Callout, NextSteps } from '../components/Docs';

const toc = [
  { id: 'root',         label: 'Root layout' },
  { id: 'backend',      label: 'Backend' },
  { id: 'frontend',     label: 'Frontend' },
  { id: 'electron',     label: 'Electron' },
  { id: 'data',         label: 'Data directory' },
  { id: 'entry-points', label: 'Key entry points' },
];

export default function ProjectStructure() {
  return (
    <DocsLayout
      title="Project Structure"
      description="File-level ownership map for the full Luna monorepo — where to find things and where to put new code."
      toc={toc}
    >
      <section>
        <h2 id="root">Root layout</h2>
        <pre><code>{`Luna/
├── backend/              # FastAPI backend — services, routers, processes
├── cli/                  # Developer CLI (luna.mjs)
├── data/                 # Runtime data — databases, models, workspace (gitignored)
├── docs/                 # Markdown architecture and process docs
├── docs-site/            # This documentation website (Next.js)
├── electron/             # Desktop shell — main process and preload bridge
├── frontend/             # React + Vite UI
├── skills/               # Version-controlled skills (shipped with repo)
├── .env.example          # Environment variable template
├── .env                  # Your local config (gitignored)
├── architecture.svg      # System architecture diagram
├── architecture_ai.svg   # AI inference and tool flow diagram
├── package.json          # Root workspace — CLI scripts
└── vercel.json           # Docs site deployment config`}</code></pre>
      </section>

      <section>
        <h2 id="backend">Backend</h2>
        <pre><code>{`backend/
├── main.py               # FastAPI bootstrap — CORS, router mounts, startup
├── config.py             # Reads .env and exposes typed config values
│
├── routers/              # HTTP route handlers — thin, delegate to services
│   ├── chat.py           # Chat streaming, conversation CRUD
│   ├── memory.py         # Facts, personality, search, compaction
│   ├── voice.py          # STT input, TTS output, emotion
│   ├── vision.py         # Screen/camera capture and analysis
│   ├── agent.py          # Skills, permissions, workspace, tasks, browser
│   ├── system.py         # Health, proactive messages, app launch, 3D scenes
│   ├── luna.py           # Dashboard — weather, markets, news aggregation
│   ├── calendar.py       # Tasks and calendar events
│   ├── spotify.py        # Spotify OAuth and playback control
│   ├── sleep.py          # Sleep tracking
│   ├── state.py          # UI and application state persistence
│   └── train.py          # Training data export
│
├── services/             # Business logic — all non-trivial code lives here
│   ├── llm.py            # LLM provider abstraction (Ollama / OpenAI-compatible)
│   ├── memory_manager.py # Fact CRUD, ChromaDB embedding, semantic search
│   ├── personality.py    # Personality state machine and scoring
│   ├── fact_extractor.py # Extract facts from conversation turns
│   ├── tool_registry.py  # Tool registration, dispatch, and permission checks
│   ├── permission_manager.py  # Load/save per-tool permission modes
│   ├── vision.py         # Camera and screen perception pipeline
│   ├── voice.py          # Audio capture, STT, TTS, emotion analysis
│   ├── web_tools.py      # Web search (DuckDuckGo) and page fetch
│   ├── browser_automation.py  # HTTP + optional Playwright browser layer
│   ├── app_launcher.py   # Launch desktop applications
│   ├── task_planner.py   # Multi-step agent task planning
│   ├── scheduler.py      # Background job orchestration
│   ├── spotify.py        # Spotify API client and token management
│   ├── activity_tracker.py    # Track user projects and activities
│   ├── away_state.py     # Idle/away detection
│   ├── media_context.py  # Current media/TV context detection
│   ├── audit_log.py      # Append-only tool action log
│   ├── workspace.py      # Agent workspace file system (data/workspace/)
│   ├── agent_tasks.py    # Agent task lifecycle management
│   └── dashboard/        # Live data providers
│       ├── weather.py    # Open-Meteo weather fetching
│       ├── markets.py    # Stock and crypto data
│       ├── news.py       # News article fetching
│       └── articles.py   # Article storage and retrieval
│
├── processes/            # Long-running background workers
│   ├── registry.py       # Register and start all background processes
│   ├── memory_maintenance/    # Fact extraction, compaction, pruning
│   ├── proactive_followups/   # Unsolicited message generation
│   ├── calendar_reminders/    # Task and event reminder dispatch
│   └── voice_runtime/         # Wake-word detection and audio capture loop
│
└── models/
    └── database.py       # SQLAlchemy models — Conversation, Message, Fact,
                          # Task, CalendarEvent, Activity, and more`}</code></pre>
      </section>

      <section>
        <h2 id="frontend">Frontend</h2>
        <pre><code>{`frontend/
├── src/
│   ├── App.tsx           # Root component — view mode routing (dev/user/luna)
│   ├── main.tsx          # Vite entry point
│   ├── index.css         # Global styles — prose, scrollbars, Tailwind base
│   │
│   ├── api/              # Typed backend request wrappers
│   │   ├── chat.ts       # Chat streaming (SSE), conversation management
│   │   ├── memory.ts     # Facts, personality, search
│   │   ├── voice.ts      # Voice input/output
│   │   ├── agent.ts      # Skills, permissions, workspace, tasks
│   │   └── system.ts     # Health, proactive, scene generation
│   │
│   ├── components/       # Feature-grouped UI components
│   │   ├── Layout/       # Sidebar, TitleBar, AwayScreen, SpeakerPicker
│   │   ├── Chat/         # ChatWindow, InputBar, MessageBubble
│   │   ├── Voice/        # VoiceOrb, PhoneMic
│   │   ├── Memory/       # MemoryPanel
│   │   ├── Luna/         # LunaDashboardView, LunaDashboardToggle
│   │   ├── Dynamic/      # DynamicWidgetOverlay, GeneratedScene, ThreeDScene
│   │   ├── Map/          # HologramMapOverlay (MapLibre GL)
│   │   ├── Calendar/     # CalendarView
│   │   ├── Activities/   # ActivitiesView
│   │   ├── Agent/        # AgentView
│   │   ├── Sleep/        # SleepView
│   │   ├── Spotify/      # SpotifyPlayer
│   │   ├── Train/        # TrainView
│   │   ├── ExtractTrain/ # ExtractTrainView
│   │   └── Auth/         # LunaLogin
│   │
│   ├── hooks/            # Reusable React hooks
│   ├── services/         # Browser/device helpers (audio, camera, visibility)
│   ├── store/
│   │   └── index.ts      # Zustand global store — all app state
│   └── types/
│       └── index.ts      # Shared TypeScript types
│
├── tailwind.config.js    # Custom luna-* colour palette and animations
├── vite.config.ts        # Proxy /api → localhost:8899
└── tsconfig.json`}</code></pre>
      </section>

      <section>
        <h2 id="electron">Electron</h2>
        <pre><code>{`electron/
├── main.js               # Main process — window creation, backend lifecycle,
│                         # tray, health-check loop, IPC handlers
├── preload.js            # contextBridge — exposes electronAPI.apiBase,
│                         # electronAPI.lunaKey, electronAPI.isElectron
├── assets/               # App icons (Windows .ico, macOS .icns)
└── package.json          # Electron build config — NSIS installer for Windows`}</code></pre>

        <Callout type="info" title="Backend process management">
          <p><code>electron/main.js</code> spawns the FastAPI backend as a child process and monitors it
          with exponential backoff restart. If the backend crashes 3 times in 60 seconds, Electron
          surfaces an error dialog rather than restarting indefinitely.</p>
        </Callout>
      </section>

      <section>
        <h2 id="data">Data directory</h2>
        <p>
          <code>data/</code> is entirely gitignored. It contains all runtime state — never commit it.
        </p>

        <pre><code>{`data/
├── luna.db               # SQLite — conversations, facts, tasks, events, activities
├── chroma/               # ChromaDB vector store for fact embeddings
├── workspace/            # Agent sandbox — files created by Luna
│   └── skills/           # User-created or agent-created skills
├── vosk-model/           # Vosk STT model (if using Vosk instead of Whisper)
├── permissions.json      # Per-tool permission mode overrides
├── spotify_token.json    # Spotify OAuth token (gitignored)
├── audit.log             # Append-only tool action log
└── backups/              # Automatic database backups`}</code></pre>
      </section>

      <section>
        <h2 id="entry-points">Key entry points</h2>
        <table>
          <thead><tr><th>File</th><th>Role</th></tr></thead>
          <tbody>
            <tr><td><code>backend/main.py</code></td><td>FastAPI startup — add routers here.</td></tr>
            <tr><td><code>backend/config.py</code></td><td>All <code>.env</code> values — read config from here, never from <code>os.environ</code> directly.</td></tr>
            <tr><td><code>backend/services/tool_registry.py</code></td><td>Register new tools here with a default permission mode.</td></tr>
            <tr><td><code>backend/processes/registry.py</code></td><td>Register new background processes here.</td></tr>
            <tr><td><code>frontend/src/App.tsx</code></td><td>View mode routing — add new top-level views here.</td></tr>
            <tr><td><code>frontend/src/store/index.ts</code></td><td>Global state — all Zustand state and actions.</td></tr>
            <tr><td><code>electron/main.js</code></td><td>Desktop lifecycle — native menus, IPC, backend launch.</td></tr>
            <tr><td><code>cli/luna.mjs</code></td><td>CLI commands — add new developer scripts here.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/architecture', label: 'Deep dive', title: 'Architecture',   desc: 'How the layers connect and the contribution boundaries between them.' },
        { href: '/contributing', label: 'Community', title: 'Contributing',   desc: 'Where new code belongs and how to write a clean PR.' },
        { href: '/api',          label: 'Platform',  title: 'API reference',  desc: 'Full HTTP endpoint documentation for every router.' },
      ]} />
    </DocsLayout>
  );
}
