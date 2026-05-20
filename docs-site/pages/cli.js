import DocsLayout from '../components/DocsLayout';

export default function CLI() {
  return (
    <DocsLayout
      title="CLI"
      description="The Luna CLI wraps repository scripts and exposes a small developer command surface."
    >
      <section>
        <h2>Usage</h2>
        <p>Run the CLI from the repo root:</p>
        <pre>
          <code>npm run luna -- &lt;command&gt;</code>
        </pre>
        <p>You can also link the CLI globally:</p>
        <pre>
          <code>npm link
luna doctor</code>
        </pre>
      </section>

      <section>
        <h2>Commands</h2>
        <ul>
          <li><strong>help</strong>: show command help.</li>
          <li><strong>doctor</strong>: verify Node, npm, and Python availability.</li>
          <li><strong>dev</strong>: start Vite and Electron together.</li>
          <li><strong>dev:lan</strong>: start dev mode with Vite exposed to the LAN.</li>
          <li><strong>backend</strong>: start only the FastAPI backend.</li>
          <li><strong>frontend</strong>: start only the Vite frontend.</li>
          <li><strong>electron</strong>: start only the Electron shell.</li>
          <li><strong>build</strong>: build the frontend.</li>
          <li><strong>dist</strong>: build the frontend and Windows Electron package.</li>
          <li><strong>check</strong>: run lightweight backend syntax checks.</li>
          <li><strong>processes</strong>: print registered backend processes as JSON.</li>
          <li><strong>clean</strong>: remove local runtime/build artifacts ignored by git.</li>
        </ul>
      </section>

      <section>
        <h2>Command Mapping</h2>
        <p>The CLI is intentionally thin and delegates to existing scripts and processes.</p>
        <p>Use the CLI for developer workflow consistency, but keep feature-specific work inside the owning package or process.</p>
      </section>
    </DocsLayout>
  );
}
