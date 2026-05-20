import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'setup',         label: 'Setup' },
  { id: 'llm',           label: 'LLM provider' },
  { id: 'embeddings',    label: 'Embeddings' },
  { id: 'lan',           label: 'LAN / network mode' },
  { id: 'spotify',       label: 'Spotify' },
  { id: 'data-services', label: 'Data services' },
  { id: 'reference',     label: 'Full reference' },
];

export default function Environment() {
  return (
    <DocsLayout
      title="Environment"
      description="Every .env key explained — LLM providers, embeddings, LAN mode, Spotify, news, weather, and markets."
      toc={toc}
    >
      <section>
        <h2 id="setup">Setup</h2>
        <p>Create your local environment file by copying the example:</p>

        <CodeFile label="terminal">
          <pre><code>{`copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux`}</code></pre>
        </CodeFile>

        <Callout type="warn" title="Never commit .env">
          <p>The <code>.env</code> file is gitignored. Do not commit it — it may contain API keys,
          your name, and local paths.</p>
        </Callout>
      </section>

      <section>
        <h2 id="llm">LLM provider</h2>
        <p>Luna supports two LLM backends. Set <code>llm_provider</code> to switch between them.</p>

        <h3>Local Ollama (default)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b`}</code></pre>
        </CodeFile>

        <p>Any model available via <code>ollama list</code> can be used. Luna was primarily tested
        with <code>qwen2.5</code> (7B and 14B) and <code>qcwind/qwen3-8b-instruct-Q4-K-M</code>. For
        best results use a model with at least 8B parameters and 8K context support.</p>

        <h3>OpenAI-compatible API (cloud or self-hosted)</h3>
        <CodeFile label=".env">
          <pre><code>{`llm_provider=openai-compatible
openai_base_url=https://api.openai.com/v1
openai_api_key=sk-...
openai_model=gpt-4o-mini`}</code></pre>
        </CodeFile>

        <p>Works with any endpoint that implements the OpenAI chat completions API — including
        LM Studio, vLLM, Together AI, Groq, and self-hosted Mistral/Llama deployments.</p>

        <Callout type="info" title="Context window">
          <p>Luna defaults to <code>num_ctx: 8192</code> and <code>num_predict: 1024</code>.
          These are set in <code>backend/services/llm.py</code> and can be adjusted for models
          that support longer contexts.</p>
        </Callout>
      </section>

      <section>
        <h2 id="embeddings">Embeddings</h2>
        <p>Embeddings power Luna's memory search — finding semantically similar facts when building context.</p>

        <CodeFile label=".env">
          <pre><code>{`# Use Ollama for embeddings (default — no extra cost)
embedding_provider=ollama
embedding_model=nomic-embed-text

# Use OpenAI-compatible embeddings API instead
embedding_provider=openai-compatible
# Uses the same openai_base_url and openai_api_key as the LLM`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="nomic-embed-text">
          <p>Pull it once with <code>ollama pull nomic-embed-text</code>. It's small (~275 MB),
          fast, and produces high-quality 768-dimension embeddings. Required for memory to work.</p>
        </Callout>
      </section>

      <section>
        <h2 id="lan">LAN / network mode</h2>
        <p>
          Luna can serve its frontend to other devices on your local network — phones, tablets,
          other laptops. You need a strong API key when you do this.
        </p>

        <CodeFile label=".env">
          <pre><code>{`# Bind to all interfaces instead of loopback only
host=0.0.0.0

# Set a strong random key — all remote requests must include this
luna_api_key=replace-with-a-64-char-random-string`}</code></pre>
        </CodeFile>

        <p>Then start the frontend with LAN binding:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- dev:lan`}</code></pre>
        </CodeFile>

        <p>Open <code>http://YOUR_LAN_IP:5173</code> on any device on your network. Enter the
        <code>luna_api_key</code> when prompted. Voice, camera, and some OS-level features are
        desktop-only — they may be unavailable on mobile browsers.</p>

        <Callout type="warn" title="Security">
          <p>Never set <code>host=0.0.0.0</code> without also setting <code>luna_api_key</code>.
          Without a key, anyone on your network can query the backend.</p>
        </Callout>
      </section>

      <section>
        <h2 id="spotify">Spotify</h2>
        <p>
          Luna can control Spotify playback — play, pause, skip, queue tracks, and respond to voice
          commands like <em>"play something chill"</em>.
        </p>
        <p>Create a Spotify Developer app at <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed' }}>developer.spotify.com/dashboard</a> and
        add <code>http://localhost:8899/api/spotify/callback</code> as a redirect URI. Then:</p>

        <CodeFile label=".env">
          <pre><code>{`spotify_client_id=your_client_id
spotify_client_secret=your_client_secret`}</code></pre>
        </CodeFile>

        <p>Trigger the OAuth flow from the Agent page in the Luna UI. The access token is stored
        locally in <code>data/spotify_token.json</code>.</p>
      </section>

      <section>
        <h2 id="data-services">Data services</h2>
        <p>These keys are optional. Luna works without them — it falls back gracefully when a service is unconfigured.</p>

        <h3>News</h3>
        <CodeFile label=".env">
          <pre><code>{`the_news_api=your_key   # https://thenewsapi.com`}</code></pre>
        </CodeFile>
        <p>Without this key the news widget is disabled. Luna will tell you news is unavailable.</p>

        <h3>Weather</h3>
        <p>Weather uses <a href="https://open-meteo.com" target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed' }}>Open-Meteo</a> by
        default — no API key required. A legacy <code>open_weather</code> key exists for older flows
        but is not needed.</p>

        <h3>Markets</h3>
        <CodeFile label=".env">
          <pre><code>{`alpha_vantage=your_key   # https://alphavantage.co`}</code></pre>
        </CodeFile>
        <p>Without this, Luna falls back to Yahoo Finance and CoinGecko for market data, which have
        rate limits but no key requirement.</p>
      </section>

      <section>
        <h2 id="reference">Full reference</h2>
        <table>
          <thead><tr><th>Key</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>user_name</code></td><td><code>friend</code></td><td>Luna uses this name when addressing you.</td></tr>
            <tr><td><code>luna_api_key</code></td><td><em>empty</em></td><td>Auth key for remote access. Leave empty for local-only use.</td></tr>
            <tr><td><code>llm_provider</code></td><td><code>ollama</code></td><td><code>ollama</code> or <code>openai-compatible</code>.</td></tr>
            <tr><td><code>ollama_base_url</code></td><td><code>http://localhost:11434</code></td><td>Ollama server URL.</td></tr>
            <tr><td><code>ollama_model</code></td><td><code>qwen2.5:7b</code></td><td>Chat model name as shown by <code>ollama list</code>.</td></tr>
            <tr><td><code>openai_base_url</code></td><td><em>empty</em></td><td>OpenAI-compatible API base URL.</td></tr>
            <tr><td><code>openai_api_key</code></td><td><em>empty</em></td><td>API key for the OpenAI-compatible provider.</td></tr>
            <tr><td><code>openai_model</code></td><td><em>empty</em></td><td>Model name for the OpenAI-compatible provider.</td></tr>
            <tr><td><code>embedding_provider</code></td><td><code>ollama</code></td><td><code>ollama</code> or <code>openai-compatible</code>.</td></tr>
            <tr><td><code>embedding_model</code></td><td><code>nomic-embed-text</code></td><td>Embedding model. Must be available via your provider.</td></tr>
            <tr><td><code>host</code></td><td><code>127.0.0.1</code></td><td>Backend bind address. Set to <code>0.0.0.0</code> for LAN access.</td></tr>
            <tr><td><code>port</code></td><td><code>8899</code></td><td>Backend HTTP port.</td></tr>
            <tr><td><code>spotify_client_id</code></td><td><em>empty</em></td><td>Spotify Developer app client ID.</td></tr>
            <tr><td><code>spotify_client_secret</code></td><td><em>empty</em></td><td>Spotify Developer app client secret.</td></tr>
            <tr><td><code>the_news_api</code></td><td><em>empty</em></td><td>TheNewsAPI key for live news widget.</td></tr>
            <tr><td><code>alpha_vantage</code></td><td><em>empty</em></td><td>Alpha Vantage key for market data.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/getting-started', label: 'Setup',    title: 'Getting started',  desc: 'Full install walkthrough if you haven\'t set up the repo yet.' },
        { href: '/voice',           label: 'Feature',  title: 'Voice setup',      desc: 'Voice-specific config keys for STT model, TTS rate, and wake word.' },
        { href: '/troubleshooting', label: 'Support',  title: 'Troubleshooting',  desc: 'Common environment and connection issues with fixes.' },
      ]} />
    </DocsLayout>
  );
}
