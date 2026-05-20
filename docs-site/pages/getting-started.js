import DocsLayout from '../components/DocsLayout';

export default function GettingStarted() {
  return (
    <DocsLayout
      title="Getting Started"
      description="Install, configure, and run L.U.N.A. locally in development mode."
    >
      <section>
        <h2>Setup</h2>
        <p>The repo is a monorepo containing the Electron shell, React frontend, FastAPI backend, and CLI tooling.</p>
        <ol>
          <li>Clone the repository to your machine.</li>
          <li>Copy <code>.env.example</code> to <code>.env</code> and update only the values you need.</li>
          <li>Install Node dependencies from the root:</li>
        </ol>
        <pre>
          <code>npm install</code>
        </pre>
        <p>Then install the frontend dependencies:</p>
        <pre>
          <code>cd frontend
npm install</code>
        </pre>
        <p>Install backend dependencies using Python:</p>
        <pre>
          <code>pip install -r backend/requirements.txt</code>
        </pre>
      </section>

      <section>
        <h2>Run Locally</h2>
        <p>Start the full stack with the repository CLI:</p>
        <pre>
          <code>npm run luna -- dev</code>
        </pre>
        <p>This launches:</p>
        <ul>
          <li>The Electron desktop shell</li>
          <li>The Vite-powered React frontend</li>
          <li>The FastAPI backend server</li>
        </ul>
        <p>If you only want one part of the stack, use:</p>
        <pre>
          <code>npm run luna -- backend
npm run luna -- frontend
npm run luna -- electron</code>
        </pre>
      </section>

      <section>
        <h2>Verify Your Setup</h2>
        <p>Common checks for contributor development:</p>
        <ul>
          <li>Backend syntax check:</li>
          <pre>
            <code>python -m py_compile backend\routers\chat.py backend\routers\system.py backend\routers\luna.py backend\services\web_tools.py backend\services\vision.py</code>
          </pre>
          <li>Frontend build:</li>
          <pre>
            <code>cd frontend
npm run build</code>
          </pre>
          <li>Use the CLI doctor command for environment sanity:</li>
          <pre>
            <code>npm run luna -- doctor</code>
          </pre>
        </ul>
      </section>

      <section>
        <h2>Troubleshooting</h2>
        <p>If the backend fails to start, check for socket bind errors and stop any older Luna backend processes.</p>
        <pre>
          <code>[Errno 10048] only one usage of each socket address is normally permitted</code>
        </pre>
        <p>Common fixes:</p>
        <ul>
          <li>Stop the older backend/Electron process</li>
          <li>Change the configured backend port in <code>.env</code></li>
          <li>Verify Python dependencies are installed</li>
        </ul>
      </section>
    </DocsLayout>
  );
}
