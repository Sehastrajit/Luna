import DocsLayout from '../components/DocsLayout';

export default function Contributing() {
  return (
    <DocsLayout
      title="Contributing"
      description="Guidelines for contributors, PR expectations, and repository best practices."
    >
      <section>
        <h2>Getting Started</h2>
        <p>Thanks for your interest in contributing to L.U.N.A.!</p>
        <ol>
          <li>Install Node.js, Python, and Ollama.</li>
          <li>Copy <code>.env.example</code> to <code>.env</code> and configure only the keys you need.</li>
          <li>Install dependencies from the root and frontend packages.</li>
          <li>Install backend Python packages with <code>pip install -r backend/requirements.txt</code>.</li>
          <li>Start the app locally with <code>npm run luna -- dev</code>.</li>
        </ol>
      </section>

      <section>
        <h2>PR Best Practices</h2>
        <ul>
          <li>Read <code>docs/ARCHITECTURE.md</code> before making broad architectural changes.</li>
          <li>Read <code>docs/PROCESSES.md</code> before changing background jobs or process behavior.</li>
          <li>Keep routers thin and move business logic into <code>backend/services/</code>.</li>
          <li>Add new runtime work to <code>backend/processes/</code> when appropriate.</li>
          <li>Keep large UI features grouped under their own component folders.</li>
          <li>Run frontend and backend checks before opening a PR.</li>
        </ul>
      </section>

      <section>
        <h2>Privacy and Security</h2>
        <p>Do not commit any secrets, local logs, runtime databases, or generated build artifacts.</p>
        <p>Keep <code>.env</code> files out of version control, and do not submit personal chat logs or tokens.</p>
      </section>
    </DocsLayout>
  );
}
