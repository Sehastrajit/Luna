import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

const navGroups = [
  {
    title: 'Overview',
    items: [
      { href: '/getting-started', label: 'Getting Started' },
      { href: '/architecture', label: 'Architecture' },
    ],
  },
  {
    title: 'Platform',
    items: [
      { href: '/cli', label: 'CLI' },
      { href: '/codebase', label: 'Codebase' },
      { href: '/project-structure', label: 'Project Structure' },
      { href: '/environment', label: 'Environment' },
    ],
  },
  {
    title: 'Community',
    items: [
      { href: '/contributing', label: 'Contributing' },
    ],
  },
];

export default function DocsLayout({ title, description, children }) {
  const router = useRouter();

  return (
    <>
      <Head>
        <title>{title} | L.U.N.A. Docs</title>
        <meta name="description" content={description} />
      </Head>

      <div className="page-shell">
        <aside className="sidebar">
          <div className="logo">L.U.N.A.</div>
          <div className="logo-subtitle">Large Unified Nexus Mind AI</div>
          <p className="sidebar-copy">Documentation for contributors, maintainers, and engineers.</p>
          <nav>
            {navGroups.map((group) => (
              <div key={group.title} className="nav-group">
                <div className="nav-group-title">{group.title}</div>
                {group.items.map((item) => {
                  const isActive =
                    router.pathname === item.href ||
                    router.asPath === item.href ||
                    router.asPath.startsWith(`${item.href}/`);

                  return (
                    <Link key={item.href} href={item.href} className={isActive ? 'nav-link active' : 'nav-link'}>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </aside>

        <main className="content">
          <header className="doc-header">
            <h1>{title}</h1>
            <p>{description}</p>
          </header>
          <div className="doc-body">{children}</div>
        </main>
      </div>
    </>
  );
}
