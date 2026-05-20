import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';

const features = [
  { title: 'Quick Start', description: 'Install, configure, and run L.U.N.A. locally.', href: '/getting-started' },
  { title: 'Architecture', description: 'Understand the backend, frontend, Electron shell, and services.', href: '/architecture' },
  { title: 'CLI', description: 'Learn the repo CLI commands and developer workflows.', href: '/cli' },
  { title: 'Codebase', description: 'Inspect the implementation structure and core entrypoints.', href: '/codebase' },
  { title: 'Contributing', description: 'Contributor guidelines, PR standards, and privacy rules.', href: '/contributing' },
  { title: 'Project Structure', description: 'Detailed repo layout and module ownership.', href: '/project-structure' },
  { title: 'Environment', description: 'Configuring .env values and runtime options.', href: '/environment' },
];

export default function Home() {
  return (
    <DocsLayout
      title="L.U.N.A. Docs"
      description="Open-source contributor documentation for the L.U.N.A. repository."
    >
      <section className="hero-panel">
        <p className="eyebrow">L.U.N.A. Open Source</p>
        <h1>Production-ready contributor documentation</h1>
        <p className="hero-copy">
          A complete docs website for repo contributors, maintainers, and developers. Browse setup,
          architecture, CLI workflows, contributing guidance, and runtime configuration.
        </p>
        <div className="hero-links">
          <Link className="button" href="/getting-started">
            Get Started
          </Link>
          <Link className="button button-secondary" href="/architecture">
            Architecture
          </Link>
        </div>
      </section>

      <section className="grid-panel">
        {features.map((feature) => (
          <Link key={feature.href} href={feature.href} className="card-link">
            <div>
              <h2>{feature.title}</h2>
              <p>{feature.description}</p>
            </div>
          </Link>
        ))}
      </section>

      <section className="summary-panel">
        <h2>What L.U.N.A. is</h2>
        <p>
          L.U.N.A. is a local-first AI companion built with Electron, React, FastAPI, and pluggable LLM providers.
          It supports chat, memory, voice, vision, dynamic widgets, dashboards, and desktop automation.
        </p>
        <p>
          Contributors can use this site as the authoritative introduction to the repository, the command
          workflows, and the architecture boundaries for clean PRs.
        </p>
      </section>
    </DocsLayout>
  );
}
