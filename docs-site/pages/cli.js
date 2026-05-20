import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'usage',     label: 'Usage' },
  { id: 'commands',  label: 'Commands' },
  { id: 'global',    label: 'Global install' },
  { id: 'workflow',  label: 'Developer workflow' },
];

export default function CLI() {
  return (
    <DocsLayout
      title="CLI"
      description="The Luna CLI wraps all developer scripts into a single consistent interface. Run, build, check, and debug the full stack from one command."
      toc={toc}
    >
      <section>
        <h2 id="usage">Usage</h2>
        <p>Run the CLI from the repository root using npm:</p>

        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- <command>`}</code></pre>
        </CodeFile>

        <p>The double dash (<code>--</code>) is required by npm to pass arguments to the script. Everything
        after it is forwarded to <code>cli/luna.mjs</code>.</p>

        <p>Show available commands:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- help`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="commands">Commands</h2>

        <table>
          <thead><tr><th>Command</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>help</code></td><td>Print command list and usage.</td></tr>
            <tr><td><code>doctor</code></td><td>Verify Node.js, npm, and Python are installed and at the right versions.</td></tr>
            <tr><td><code>dev</code></td><td>Start Vite and Electron together (full desktop stack).</td></tr>
            <tr><td><code>dev:lan</code></td><td>Start with Vite bound to <code>0.0.0.0</code> for LAN access from other devices.</td></tr>
            <tr><td><code>backend</code></td><td>Start only the FastAPI backend on port 8899.</td></tr>
            <tr><td><code>frontend</code></td><td>Start only the Vite dev server on port 5173.</td></tr>
            <tr><td><code>electron</code></td><td>Start only the Electron shell (backend must already be running).</td></tr>
            <tr><td><code>build</code></td><td>Build the frontend for production (<code>frontend/dist/</code>).</td></tr>
            <tr><td><code>dist</code></td><td>Build the frontend and package the Windows NSIS installer.</td></tr>
            <tr><td><code>check</code></td><td>Run lightweight Python syntax checks on critical backend files.</td></tr>
            <tr><td><code>processes</code></td><td>Print all registered backend background processes as JSON.</td></tr>
            <tr><td><code>clean</code></td><td>Remove local runtime and build artefacts that are gitignored.</td></tr>
          </tbody>
        </table>

        <h3>doctor</h3>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- doctor`}</code></pre>
        </CodeFile>
        <p>Expected output on a healthy machine:</p>
        <CodeFile label="output">
          <pre><code>{`✓ Node.js 20.x found
✓ npm 10.x found
✓ Python 3.11 found
✓ Backend syntax OK`}</code></pre>
        </CodeFile>

        <h3>check</h3>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- check`}</code></pre>
        </CodeFile>
        <p>Runs <code>python -m py_compile</code> on the critical backend entry points — a fast sanity
        check that catches import errors and syntax mistakes before opening a PR.</p>

        <h3>processes</h3>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- processes`}</code></pre>
        </CodeFile>
        <p>Outputs a JSON list of every process registered with the backend, including name, schedule,
        and current status. Useful for debugging background job issues.</p>

        <h3>clean</h3>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- clean`}</code></pre>
        </CodeFile>
        <p>Deletes <code>frontend/dist/</code>, <code>electron/dist/</code>, and any other gitignored
        build artefacts. Does <strong>not</strong> touch <code>data/</code> — your memory and runtime
        data are preserved.</p>

        <Callout type="warn" title="clean does not delete data/">
          <p>If you want to fully reset Luna's memory, personality, and conversation history, manually
          delete <code>data/luna.db</code> and <code>data/chroma/</code>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="global">Global install</h2>
        <p>
          You can link the CLI globally so you can run <code>luna</code> from anywhere instead of
          <code>npm run luna --</code>:
        </p>

        <CodeFile label="terminal">
          <pre><code>{`# From the repo root — links the CLI to your global npm bin
npm link

# Now run from anywhere
luna dev
luna doctor
luna check`}</code></pre>
        </CodeFile>

        <p>To unlink later:</p>
        <CodeFile label="terminal">
          <pre><code>{`npm unlink`}</code></pre>
        </CodeFile>

        <Callout type="info" title="Windows PATH">
          <p>On Windows, npm's global bin directory must be on your <code>PATH</code>. If <code>luna</code>
          isn't found after linking, run <code>npm config get prefix</code> and add that path's
          <code>\bin</code> subdirectory to your environment variables.</p>
        </Callout>
      </section>

      <section>
        <h2 id="workflow">Developer workflow</h2>
        <p>Typical flow for a feature PR:</p>

        <CodeFile label="terminal">
          <pre><code>{`# 1. Verify dependencies
npm run luna -- doctor

# 2. Start full stack for development
npm run luna -- dev

# 3. Make your changes in frontend/ or backend/

# 4. Check backend syntax hasn't broken
npm run luna -- check

# 5. Build frontend to catch TypeScript errors
cd frontend && npm run build && cd ..

# 6. Open PR`}</code></pre>
        </CodeFile>

        <p>If you only need the backend running (e.g. testing API changes with curl):</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run luna -- backend
# In another terminal:
curl http://localhost:8899/health`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/contributing',     label: 'Community', title: 'Contributing',      desc: 'Branch conventions, PR checklist, and architecture rules.' },
        { href: '/project-structure',label: 'Platform',  title: 'Project structure', desc: 'Where every file lives in the monorepo.' },
        { href: '/troubleshooting',  label: 'Support',   title: 'Troubleshooting',   desc: 'Fix common build, port, and backend issues.' },
      ]} />
    </DocsLayout>
  );
}
