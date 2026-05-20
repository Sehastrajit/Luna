import DocsLayout from '../components/DocsLayout';

export default function Architecture() {
  return (
    <DocsLayout
      title="Architecture"
      description="Understand the layered architecture, repository boundaries, and backend/frontend responsibilities."
    >
      <section>
        <h2>High-Level Layers</h2>
        <p>L.U.N.A. is built from three main application layers and a shared service layer:</p>
        <ol>
          <li>Electron shell and desktop runtime</li>
          <li>React/Vite frontend UI</li>
          <li>FastAPI backend services</li>
        </ol>
        <figure className="doc-figure">
          <img src="/images/architecture.svg" alt="LUNA architecture diagram" />
          <figcaption>High-level architecture with the Electron shell, frontend, backend, and shared service layer.</figcaption>
        </figure>
      </section>

      <section>
        <h2>Backend</h2>
        <p>The backend lives under <code>backend/</code> and is responsible for API routes, business logic, integrations, and runtime processes.</p>
        <ul>
          <li><code>backend/main.py</code>: FastAPI app bootstrap, middleware, and router registration.</li>
          <li><code>backend/routers/</code>: thin HTTP routes that delegate logic to services.</li>
          <li><code>backend/services/</code>: core feature logic, integrations, local model calls, and background workflows.</li>
          <li><code>backend/models/</code>: database schemas and request/response models.</li>
        </ul>
      </section>

      <section>
        <h2>Frontend</h2>
        <p>The frontend is located in <code>frontend/</code> and renders the browser and Electron UI.</p>
        <ul>
          <li><code>frontend/src/api/</code>: typed API clients and request wrappers.</li>
          <li><code>frontend/src/components/</code>: feature-based UI components.</li>
          <li><code>frontend/src/hooks/</code>: reusable React hooks.</li>
          <li><code>frontend/src/services/</code>: browser and device service helpers.</li>
          <li><code>frontend/src/store/</code>: global application state management.</li>
          <li><code>frontend/src/types/</code>: shared TypeScript types.</li>
        </ul>
      </section>

      <section>
        <h2>Electron</h2>
        <p>The Electron shell is under <code>electron/</code> and handles the desktop lifecycle.</p>
        <ul>
          <li><code>electron/main.js</code>: window creation, tray, backend process lifecycle, and native event handling.</li>
          <li><code>electron/preload.js</code>: renderer-safe API bridge for the frontend.</li>
          <li><code>electron/assets/</code>: icons and platform-specific desktop assets.</li>
        </ul>
      </section>

      <section>
        <h2>Skills and Extensions</h2>
        <p>Optional skills are stored in <code>skills/</code>. Each skill includes:</p>
        <ul>
          <li><code>skill.json</code>: metadata and manifest</li>
          <li><code>SKILL.md</code>: skill description and usage</li>
        </ul>
      </section>

      <section>
        <h2>Contribution Boundaries</h2>
        <p>Keep changes scoped to one area when possible:</p>
        <ul>
          <li>Backend logic in <code>backend/services/</code>, not in routers.</li>
          <li>Frontend UI in component folders and feature-based views.</li>
          <li>Desktop-specific work limited to <code>electron/</code>.</li>
          <li>Background jobs under <code>backend/processes/</code>.</li>
        </ul>
        <p>Use <code>docs/ARCHITECTURE.md</code> and <code>docs/PROCESSES.md</code> as the source of truth for architecture and process design.</p>
      </section>
    </DocsLayout>
  );
}
