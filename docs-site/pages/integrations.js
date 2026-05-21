import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'llm',       label: 'LLM providers' },
  { id: 'voice',     label: 'Voice engines' },
  { id: 'apps',      label: 'Desktop apps' },
  { id: 'data',      label: 'Live data & APIs' },
  { id: 'platforms', label: 'Platforms' },
];

const Badge = ({ label, color = 'purple' }) => {
  return (
    <span className={`int-badge int-badge-${color}`}>{label}</span>
  );
};

const Card = ({ icon, title, subtitle, badges = [], note }) => (
  <div className="int-card">
    <div className="int-icon">{icon}</div>
    <div className="int-card-body">
      <div className="int-card-head">
        <span className="int-title">{title}</span>
        {badges.map(b => <Badge key={b.label} label={b.label} color={b.color} />)}
      </div>
      {subtitle && <p className="int-subtitle">{subtitle}</p>}
      {note    && <p className="int-note">{note}</p>}
    </div>
  </div>
);

const Grid = ({ children }) => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
    {children}
  </div>
);

const PlatformCard = ({ icon, name, status, detail }) => (
  <div className="int-platform-card">
    <div className="int-platform-icon">{icon}</div>
    <div className="int-platform-name">{name}</div>
    <div className="int-platform-status"><Badge label={status} color={status === 'Full support' ? 'green' : status === 'Partial' ? 'blue' : 'gray'} /></div>
    <div className="int-detail">{detail}</div>
  </div>
);

export default function Integrations() {
  return (
    <DocsLayout
      title="Integrations"
      description="Every LLM provider, desktop app, data service, voice engine, and platform that L.U.N.A. works with."
      toc={toc}
    >

      <p>
        Luna is built to plug into what you already use. Every integration is configured in
        <code>.env</code> — no code changes needed. Local integrations require no API key;
        cloud ones are always opt-in.
      </p>

      {/* ── LLM Providers ── */}
      <section>
        <h2 id="llm">LLM Providers</h2>
        <p>
          Luna talks to any OpenAI-compatible endpoint. Switch models by changing two lines in
          <code>.env</code> — no restart of anything else.
        </p>

        <Card
          icon="🦙"
          title="Ollama"
          subtitle="Runs models locally on your machine. The default provider. No API key, no internet required. Supports GPU acceleration via CUDA or Metal."
          badges={[{ label: 'Local', color: 'green' }, { label: 'Default', color: 'purple' }]}
          note="ollama_base_url=http://localhost:11434  ·  llm_provider=ollama"
        />
        <Card
          icon="⚡"
          title="Groq"
          subtitle="Fastest cloud inference available. LLaMA 3.3 70B at ~300 tok/s. Free tier available. OpenAI-compatible."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Fast', color: 'purple' }]}
          note="openai_base_url=https://api.groq.com/openai/v1  ·  openai_model=llama-3.3-70b-versatile"
        />
        <Card
          icon="🌐"
          title="OpenRouter"
          subtitle="One API key for every major model: Claude, Gemini, GPT-4o, Mistral, Llama, Command R, and more. Pay-per-token, no subscriptions."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Any model', color: 'purple' }]}
          note="openai_base_url=https://openrouter.ai/api/v1"
        />
        <Card
          icon="🤖"
          title="OpenAI"
          subtitle="GPT-4o, GPT-4o mini, o1, and future models. Official OpenAI API."
          badges={[{ label: 'Cloud', color: 'blue' }]}
          note="openai_base_url=https://api.openai.com/v1  ·  openai_model=gpt-4o"
        />
        <Card
          icon="🔬"
          title="LM Studio"
          subtitle="Local model server with a GUI. Exposes an OpenAI-compatible endpoint. Good for trying new GGUF models without configuring Ollama."
          badges={[{ label: 'Local', color: 'green' }]}
          note="openai_base_url=http://localhost:1234/v1  ·  openai_api_key=lm-studio"
        />
        <Card
          icon="🦾"
          title="llama.cpp server"
          subtitle="Minimal OpenAI-compatible server built from llama.cpp. Maximum control over quantization and hardware."
          badges={[{ label: 'Local', color: 'green' }]}
          note="openai_base_url=http://localhost:8080/v1"
        />
        <Card
          icon="🏠"
          title="Jan.ai"
          subtitle="Open-source local model manager with a desktop GUI. Exposes an OpenAI-compatible API on localhost."
          badges={[{ label: 'Local', color: 'green' }]}
          note="openai_base_url=http://localhost:1337/v1"
        />

        <Callout type="info" title="Setting the provider">
          <p>All non-Ollama providers use the same two config keys:</p>
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://...
openai_api_key=sk-...
openai_model=model-name-here`}</code></pre>
          <p style={{ margin: '8px 0 0' }}>See the <a href="/environment#llm" style={{ color: '#7c3aed' }}>Environment</a> page for the full key reference.</p>
        </Callout>

        <h3>Models known to work well</h3>
        <table>
          <thead><tr><th>Model</th><th>Provider</th><th>Good for</th></tr></thead>
          <tbody>
            <tr><td><code>qwen2.5:7b</code></td><td>Ollama (local)</td><td>Daily driver — fast, tool-calling, 8 GB VRAM</td></tr>
            <tr><td><code>qwen2.5:14b</code></td><td>Ollama (local)</td><td>Better reasoning, 12 GB VRAM</td></tr>
            <tr><td><code>llama3.2:3b</code></td><td>Ollama (local)</td><td>Low-end hardware, 4 GB VRAM</td></tr>
            <tr><td><code>llama-3.3-70b-versatile</code></td><td>Groq</td><td>Best quality + speed in cloud</td></tr>
            <tr><td><code>anthropic/claude-opus-4</code></td><td>OpenRouter</td><td>Complex reasoning tasks</td></tr>
            <tr><td><code>google/gemini-2.5-pro</code></td><td>OpenRouter</td><td>Long context, multimodal</td></tr>
            <tr><td><code>gpt-4o-mini</code></td><td>OpenAI</td><td>Budget cloud option</td></tr>
          </tbody>
        </table>
      </section>

      {/* ── Voice engines ── */}
      <section>
        <h2 id="voice">Voice Engines</h2>
        <p>Voice runs entirely on your machine. No audio is sent to external servers unless you configure a cloud TTS.</p>

        <h3>Speech-to-text (STT)</h3>
        <Card
          icon="🎙"
          title="faster-whisper"
          subtitle="OpenAI Whisper reimplemented in CTranslate2. Runs locally, significantly faster than the original. Recommended."
          badges={[{ label: 'Local', color: 'green' }, { label: 'Default', color: 'purple' }]}
          note="whisper_model=base  (tiny / base / small / medium / large)"
        />
        <Card
          icon="🔊"
          title="Vosk"
          subtitle="Offline speech recognition toolkit. Very fast, low memory footprint, good for wake-word detection on low-end hardware."
          badges={[{ label: 'Local', color: 'green' }]}
          note="voice_runtime=vosk"
        />

        <h3>Text-to-speech (TTS)</h3>
        <Card
          icon="🔉"
          title="edge-tts"
          subtitle="Microsoft Edge neural TTS voices. High quality, 300+ voices and languages. Requires an internet connection — audio is synthesised by Microsoft's servers."
          badges={[{ label: 'Cloud', color: 'blue' }, { label: 'Default', color: 'purple' }]}
          note="tts_provider=edge-tts"
        />
        <Card
          icon="💬"
          title="pyttsx3"
          subtitle="Fully offline TTS using the OS voice engine (SAPI5 on Windows, NSSpeechSynthesizer on macOS, eSpeak on Linux). No internet required."
          badges={[{ label: 'Local', color: 'green' }]}
          note="tts_provider=pyttsx3  ·  tts_voice_index=0"
        />

        <p>
          For the full STT/TTS config options and model tradeoff table, see the{' '}
          <a href="/voice" style={{ color: '#7c3aed' }}>Voice</a> page.
        </p>
      </section>

      {/* ── Desktop apps ── */}
      <section>
        <h2 id="apps">Desktop Apps &amp; Automation</h2>
        <p>
          Luna can control these through natural language. Each action goes through the permission
          system — <code>allow</code>, <code>confirm</code>, or <code>block</code> per tool.
        </p>

        <Card
          icon="🎵"
          title="Spotify"
          subtitle='Playback control, queue management, search, and now-playing display. Trigger with phrases like "play something chill" or "skip this".'
          badges={[{ label: 'Opt-in', color: 'blue' }]}
          note="Requires spotify_client_id and spotify_client_secret in .env. See Environment → Spotify."
        />
        <Card
          icon="🌐"
          title="Web browser"
          subtitle="Open URLs, navigate to pages, and read public page content. Playwright can be enabled for full browser automation including JavaScript-rendered pages."
          badges={[{ label: 'Built-in', color: 'purple' }]}
          note="Public HTTP fetch is always available. Playwright requires: pip install playwright && playwright install chromium"
        />
        <Card
          icon="🖥"
          title="App launcher"
          subtitle='Launch any installed application by name. Luna resolves common app names to their executable paths on Windows, macOS, and Linux. Say "open calculator" or "launch VS Code".'
          badges={[{ label: 'Built-in', color: 'purple' }]}
        />
        <Card
          icon="📅"
          title="Calendar &amp; tasks"
          subtitle="Create, list, update, and complete tasks stored in Luna's local SQLite database. Triggers proactive follow-up reminders when due."
          badges={[{ label: 'Built-in', color: 'purple' }]}
        />
        <Card
          icon="🔍"
          title="Web search"
          subtitle="DuckDuckGo HTML search — no API key required. Luna fetches and parses results automatically when a model tool call requests live information."
          badges={[{ label: 'Built-in', color: 'purple' }]}
        />
        <Card
          icon="🔊"
          title="Audio device switcher"
          subtitle="Switch the default Windows audio output device by name. Useful for toggling between headphones, speakers, and virtual devices."
          badges={[{ label: 'Windows only', color: 'gray' }]}
        />
        <Card
          icon="🗺"
          title="Maps"
          subtitle="Open interactive MapLibre map overlays with a location query. Geocoding via the map tile provider. Works in the browser and Electron UI."
          badges={[{ label: 'Built-in', color: 'purple' }]}
        />
      </section>

      {/* ── Live data ── */}
      <section>
        <h2 id="data">Live Data &amp; APIs</h2>
        <p>These feed the Luna dashboard and the LLM's context. All are opt-in except Open-Meteo.</p>

        <Card
          icon="⛅"
          title="Open-Meteo"
          subtitle="Free, no-key weather API. Returns current conditions and forecasts for any coordinates. This is the default weather provider."
          badges={[{ label: 'Free', color: 'green' }, { label: 'No key', color: 'green' }]}
          note="Set weather_lat, weather_lon, weather_city, weather_timezone in .env."
        />
        <Card
          icon="📰"
          title="TheNewsAPI"
          subtitle="Live top headlines and category-filtered news articles for the dashboard. Falls back to RSS when no key is configured."
          badges={[{ label: 'Opt-in', color: 'blue' }]}
          note="the_news_api=your-key"
        />
        <Card
          icon="📈"
          title="Yahoo Finance"
          subtitle="Stock quotes and market data. Used by default for equities in the dashboard — no API key required."
          badges={[{ label: 'No key', color: 'green' }]}
        />
        <Card
          icon="🪙"
          title="CoinGecko"
          subtitle="Cryptocurrency prices and market cap data. Used by default for crypto widgets — no API key required."
          badges={[{ label: 'No key', color: 'green' }]}
        />
        <Card
          icon="📊"
          title="Alpha Vantage"
          subtitle="Extended stock market data and technical indicators. Used as an alternative data source when configured."
          badges={[{ label: 'Opt-in', color: 'blue' }]}
          note="alpha_vantage=your-key"
        />
      </section>

      {/* ── Platforms ── */}
      <section>
        <h2 id="platforms">Platforms</h2>
        <p>Where Luna runs and what works on each platform.</p>

        <Grid>
          <PlatformCard
            icon="🪟"
            name="Windows"
            status="Full support"
            detail="Electron desktop app, voice input/output, app launcher, audio switcher, Spotify, camera, screen vision. Primary development target."
          />
          <PlatformCard
            icon="🍎"
            name="macOS"
            status="Full support"
            detail="Electron desktop app, voice input/output, app launcher, Spotify. Audio switcher not available (Windows-only). Tested on Apple Silicon."
          />
          <PlatformCard
            icon="🐧"
            name="Linux"
            status="Full support"
            detail="Electron desktop app. Voice works with PortAudio. pyttsx3 uses eSpeak. Audio switcher not available. Best with Docker."
          />
          <PlatformCard
            icon="🐳"
            name="Docker"
            status="Partial"
            detail="Full chat, memory, tools, and API. Voice, Electron shell, and OS-level automation are desktop-only. Any device with Docker installed."
          />
          <PlatformCard
            icon="📱"
            name="Phone / Tablet"
            status="Partial"
            detail="Browser access via local network (LAN mode). Chat and dashboard work fully. Voice depends on browser microphone permissions."
          />
          <PlatformCard
            icon="💻"
            name="Second computer"
            status="Partial"
            detail="Any machine on your LAN can connect to the same Luna backend via browser. Set host=0.0.0.0 and a luna_api_key in .env."
          />
        </Grid>

        <Callout type="info" title="LAN / multi-device access">
          <pre><code>{`# .env
host=0.0.0.0
luna_api_key=replace-with-a-strong-random-key`}</code></pre>
          <p style={{ margin: '8px 0 0' }}>
            Then open <code>http://YOUR-LAN-IP:8899</code> on any device. Set a strong
            <code>luna_api_key</code> — without it, anyone on the network can access your Luna.
          </p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/environment', label: 'Config', title: 'Environment', desc: 'Every .env key for all providers, with defaults and examples.' },
        { href: '/voice',       label: 'Voice',  title: 'Voice',       desc: 'STT/TTS model details, wake word config, and tradeoff table.' },
        { href: '/agent',       label: 'Agent',  title: 'Agent & Skills', desc: 'Permission system, tool registry, and custom skills.' },
      ]} />
    </DocsLayout>
  );
}
