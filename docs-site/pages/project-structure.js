import DocsLayout from '../components/DocsLayout';

export default function ProjectStructure() {
  return (
    <DocsLayout
      title="Project Structure"
      description="A detailed breakdown of the Luna repository layout and module ownership."
    >
      <section>
        <h2>Root Layout</h2>
        <p>The root repository contains the shell for the monorepo with workspace-aware package scripts.</p>
        <ul>
          <li><code>cli/</code>: the Luna CLI entrypoint</li>
          <li><code>backend/</code>: FastAPI backend, routers, services, models, and processes</li>
          <li><code>frontend/</code>: React + Vite app with UI, API clients, and state</li>
          <li><code>electron/</code>: desktop shell, preload bridge, icons, and packaging helpers</li>
          <li><code>docs/</code>: markdown documentation, architecture, process guides, and workflows</li>
          <li><code>skills/</code>: optional assistant skills and manifests</li>
        </ul>
      </section>

      <section>
        <h2>Backend Structure</h2>
        <ul>
          <li><code>backend/main.py</code> — FastAPI startup and router registration.</li>
          <li><code>backend/routers/</code> — thin HTTP endpoints for chat, system, memory, vision, and tools.</li>
          <li><code>backend/services/</code> — core business logic, external provider integration, AI orchestration, tools, and background helpers.</li>
          <li><code>backend/processes/</code> — registered periodic and runtime background workers.</li>
          <li><code>backend/models/</code> — database models and API schema validation.</li>
        </ul>
      </section>

      <section>
        <h2>Frontend Structure</h2>
        <ul>
          <li><code>frontend/src/api/</code> — backend request wrappers and typed endpoints.</li>
          <li><code>frontend/src/components/</code> — feature-based UI components, views, and widgets.</li>
          <li><code>frontend/src/hooks/</code> — reusable logic for state, events, and effects.</li>
          <li><code>frontend/src/services/</code> — browser and device helpers for camera, audio, and visibility.</li>
          <li><code>frontend/src/store/</code> — global state and persistent client-side stores.</li>
          <li><code>frontend/src/types/</code> — shared TypeScript types for API data and UI models.</li>
        </ul>
      </section>

      <section>
        <h2>Electron Structure</h2>
        <ul>
          <li><code>electron/main.js</code> — app shell, native menus, backend process management, and IPC.</li>
          <li><code>electron/preload.js</code> — secure API bridge to expose selective functionality to the renderer.</li>
          <li><code>electron/assets/</code> — application icons and assets used by the desktop app.</li>
        </ul>
      </section>
    </DocsLayout>
  );
}
