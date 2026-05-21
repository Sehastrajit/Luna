import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'prerequisites', label: 'Prerequisites' },
  { id: 'ollama',        label: 'Install Ollama' },
  { id: 'install',       label: 'Install dependencies' },
  { id: 'configure',     label: 'Configure .env' },
  { id: 'first-run',     label: 'First run' },
  { id: 'verify',        label: 'Verify setup' },
  { id: 'next',          label: 'Next steps' },
];

export default function GettingStarted() {
  return (
    <DocsLayout
      title="Getting Started"
      description="Install Ollama, pull models, configure your environment, and run L.U.N.A. locally in under 10 minutes."
      toc={toc}
    >
      <section>
        <h2 id="prerequisites">Prerequisites</h2>
        <p>You need the following tools installed before cloning the repo:</p>

        <table>
          <thead><tr><th>Tool</th><th>Minimum version</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td>Node.js</td><td>18.x</td><td>Required by Electron and Vite. Use <code>node --version</code> to check.</td></tr>
            <tr><td>npm</td><td>9.x</td><td>Ships with Node.js. Run <code>npm --version</code>.</td></tr>
            <tr><td>Python</td><td>3.10+</td><td>Required by the FastAPI backend and all ML dependencies.</td></tr>
            <tr><td>pip</td><td>23+</td><td>Run <code>pip --version</code>. Upgrade with <code>pip install --upgrade pip</code>.</td></tr>
            <tr><td>Ollama</td><td>Latest</td><td>Provides local LLM inference. See the section below.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="ollama">Install Ollama and pull models</h2>
        <p>
          Luna uses Ollama by default for LLM inference and embeddings. Download and install it from{' '}
          <a href="https://ollama.com" target="_blank" rel="noopener noreferrer" style={{ color: '#7c3aed' }}>ollama.com</a>,
          then pull the required models.
        </p>

        <p><strong>Chat model</strong> — pick one based on your hardware:</p>

        <CodeFile label="terminal">
          <pre><code>{`# Recommended — runs well on 8GB VRAM or 16GB RAM
ollama pull qwen2.5:7b

# Higher quality — needs 16GB+ VRAM or 32GB RAM
ollama pull qwen2.5:14b

# Lightweight — for low-end hardware
ollama pull qwen2.5:3b`}</code></pre>
        </CodeFile>

        <p><strong>Embedding model</strong> — required for memory search:</p>

        <CodeFile label="terminal">
          <pre><code>{`ollama pull nomic-embed-text`}</code></pre>
        </CodeFile>

        <p><strong>Vision model</strong> — optional, enables screen/camera awareness:</p>

        <CodeFile label="terminal">
          <pre><code>{`ollama pull moondream`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="Verify Ollama is running">
          <p>Run <code>ollama list</code> to confirm your models are downloaded. Ollama must be running
          before you start Luna — it listens on <code>http://localhost:11434</code> by default.</p>
        </Callout>
      </section>

      <section>
        <h2 id="install">Install dependencies</h2>

        <Steps>
          <Step num={1} title="Clone the repository">
            <CodeFile label="terminal">
              <pre><code>{`git clone https://github.com/luna-ai-project/Luna.git
cd Luna`}</code></pre>
            </CodeFile>
          </Step>

          <Step num={2} title="Install root and frontend Node.js packages">
            <CodeFile label="terminal">
              <pre><code>{`npm install
cd frontend && npm install && cd ..`}</code></pre>
            </CodeFile>
          </Step>

          <Step num={3} title="Install Python backend dependencies">
            <CodeFile label="terminal">
              <pre><code>{`pip install -r backend/requirements.txt`}</code></pre>
            </CodeFile>
            <Callout type="warn" title="Python environment">
              <p>Use a virtual environment to avoid dependency conflicts:
              <code>python -m venv .venv && .venv\Scripts\activate</code> (Windows) or
              <code>source .venv/bin/activate</code> (macOS/Linux), then run pip install.</p>
            </Callout>
          </Step>
        </Steps>
      </section>

      <section>
        <h2 id="configure">Configure .env</h2>
        <p>Copy the example environment file and set your values:</p>

        <CodeFile label="terminal">
          <pre><code>{`copy .env.example .env`}</code></pre>
        </CodeFile>

        <p>Open <code>.env</code> and set at minimum:</p>

        <CodeFile label=".env">
          <pre><code>{`# Your name — Luna uses this to personalise responses
user_name=your_name

# LLM provider — 'ollama' for local, 'openai-compatible' for cloud
llm_provider=ollama
ollama_base_url=http://localhost:11434
ollama_model=qwen2.5:7b

# Embedding model for memory search
embedding_provider=ollama
embedding_model=nomic-embed-text`}</code></pre>
        </CodeFile>

        <Callout type="note" title="luna_api_key">
          <p>Leave <code>luna_api_key</code> empty for local-only development. Set a strong random value
          only if you expose the app to other devices on your network (LAN mode).</p>
        </Callout>
      </section>

      <section>
        <h2 id="first-run">First run</h2>
        <p>Start the full stack — Electron shell, Vite frontend, and FastAPI backend — with a single command:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- dev`}</code></pre>
        </CodeFile>

        <p>This starts three processes concurrently:</p>
        <ul>
          <li>FastAPI backend on <code>http://localhost:8899</code></li>
          <li>Vite dev server on <code>http://localhost:5173</code></li>
          <li>Electron desktop window loading the Vite URL</li>
        </ul>

        <p>You can also start individual parts if you don't need the desktop shell:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- backend    # FastAPI only
npm run luna -- frontend   # Vite only (opens in browser)
npm run luna -- electron   # Electron only (backend must be running)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="verify">Verify your setup</h2>
        <p>Run the built-in doctor command to check all dependencies are available:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- doctor`}</code></pre>
        </CodeFile>

        <p>Expected output:</p>
        <CodeFile label="output">
          <pre><code>{`✓ Node.js 20.x
✓ npm 10.x
✓ Python 3.11
✓ Backend syntax OK`}</code></pre>
        </CodeFile>

        <p>Check the backend is healthy:</p>
        <CodeFile label="terminal">
          <pre><code>{`curl http://localhost:8899/health`}</code></pre>
        </CodeFile>

        <p>Run a backend syntax check before opening a PR:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- check`}</code></pre>
        </CodeFile>

        <Callout type="warn" title="Port 8899 already in use">
          <p>If the backend won't start, another Luna process is probably already running.
          Kill it or change the port in <code>.env</code> with <code>port=8900</code>. See
          the <a href="/troubleshooting" style={{ color: '#7c3aed' }}>Troubleshooting</a> page for more.</p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/architecture', label: 'Deep dive',   title: 'Architecture',    desc: 'Understand how the three layers interact and how a message flows from input to response.' },
        { href: '/environment',  label: 'Config',      title: 'Environment',     desc: 'Full reference for every .env key including Spotify, news, weather, and LAN mode.' },
        { href: '/voice',        label: 'Feature',     title: 'Voice setup',     desc: 'Configure wake-word detection, push-to-talk, TTS voice, and STT model.' },
        { href: '/contributing', label: 'Community',   title: 'Contributing',    desc: 'Branch conventions, PR checklist, architecture rules, and how to get a PR merged.' },
      ]} />
    </DocsLayout>
  );
}
