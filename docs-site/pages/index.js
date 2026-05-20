import Head from 'next/head';
import Link from 'next/link';

const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
  </svg>
);

const LinkedInIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
);

const features = [
  { icon: '🎙️', title: 'Voice', desc: 'Wake-word detection and push-to-talk. Luna listens, understands, and speaks back with local TTS.' },
  { icon: '🧠', title: 'Memory', desc: 'Persistent facts, personality state, and conversation summaries — stored in local SQLite and ChromaDB.' },
  { icon: '👁️', title: 'Vision', desc: 'Screen and camera awareness. Luna builds temporal visual context without storing raw frames.' },
  { icon: '⚡', title: 'Automation', desc: 'Launch apps, control the browser, manage Spotify, execute calendar tasks and desktop actions.' },
  { icon: '📊', title: 'Dashboard', desc: 'Live news, markets, weather, and maps in a heads-up display widget layer.' },
  { icon: '🔒', title: 'Private by Default', desc: 'Inference runs on your machine via Ollama. Zero data leaves unless you opt into cloud features.' },
];

const steps = [
  { title: 'Speak or type', desc: 'Chat through the UI or trigger Luna by voice. Accepts text, voice, and vision frames as input.' },
  { title: 'Context assembled', desc: 'Memory facts, personality, calendar state, vision observations, and activity history are injected into the prompt.' },
  { title: 'LLM processes', desc: 'Your local Ollama model or any OpenAI-compatible API handles inference with a full context window.' },
  { title: 'Actions & response', desc: 'Luna streams the reply, executes tools, opens widgets, updates memory, and delivers voice output.' },
];

/* Floating sea particles */
const particles = [
  { top: '58%', left: '8%',  size: 3, delay: '0s',    dur: '6s' },
  { top: '72%', left: '22%', size: 2, delay: '1.2s',  dur: '8s' },
  { top: '65%', left: '40%', size: 4, delay: '2.4s',  dur: '7s' },
  { top: '80%', left: '55%', size: 2, delay: '0.6s',  dur: '9s' },
  { top: '60%', left: '70%', size: 3, delay: '3.1s',  dur: '6s' },
  { top: '75%', left: '85%', size: 2, delay: '1.8s',  dur: '8s' },
  { top: '68%', left: '94%', size: 3, delay: '0.3s',  dur: '7s' },
  { top: '85%', left: '12%', size: 2, delay: '2.1s',  dur: '9s' },
  { top: '62%', left: '32%', size: 2, delay: '4.0s',  dur: '7s' },
  { top: '78%', left: '62%', size: 3, delay: '1.5s',  dur: '6s' },
];

export default function Home() {
  return (
    <>
      <Head>
        <title>L.U.N.A. — Local AI Companion</title>
        <meta name="description" content="L.U.N.A. is a local-first AI companion with voice, memory, vision, and automation. Runs entirely on your machine." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/images/logo.svg" type="image/svg+xml" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
        <style>{`
          @keyframes wave-drift-fwd { from { transform: translateX(0); } to { transform: translateX(-50%); } }
          @keyframes wave-drift-rev { from { transform: translateX(-50%); } to { transform: translateX(0); } }
          @keyframes sea-particle {
            0%   { transform: translateY(0) scale(1);    opacity: 0; }
            15%  { opacity: 0.85; }
            80%  { opacity: 0.35; }
            100% { transform: translateY(-80px) scale(0.4); opacity: 0; }
          }
          @keyframes moon-glow {
            0%, 100% { opacity: 0.65; transform: scale(1); }
            50%      { opacity: 0.85; transform: scale(1.06); }
          }
          @keyframes reflection-shimmer {
            0%, 100% { opacity: 0.22; transform: scaleX(1) translateY(0); }
            33%      { opacity: 0.32; transform: scaleX(1.04) translateY(-6px); }
            66%      { opacity: 0.18; transform: scaleX(0.97) translateY(4px); }
          }
        `}</style>
      </Head>

      <div className="lp-root">

        {/* ── Nav ── */}
        <nav className="site-nav">
          <div className="site-nav-inner">
            <Link href="/" className="site-nav-brand" aria-label="L.U.N.A. home">
              <img src="/images/logo.svg" alt="" width={26} height={26} />
              <span className="site-nav-logo">L.U.N.A.</span>
            </Link>
            <div className="site-nav-links">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="site-nav-link">
                <GitHubIcon /><span>GitHub</span>
              </a>
              <a href="https://www.linkedin.com/in/sehastrajit-s/" target="_blank" rel="noopener noreferrer" className="site-nav-link">
                <LinkedInIcon /><span>LinkedIn</span>
              </a>
              <div className="site-nav-divider" aria-hidden="true" />
              <Link href="/workflow" className="site-nav-link"><span>Workflow</span></Link>
              <Link href="/getting-started" className="site-nav-cta">Docs →</Link>
            </div>
          </div>
        </nav>

        {/* ── Hero ── */}
        <section className="lp-hero" style={{ background: '#02020a', overflow: 'hidden' }}>

          {/* Moon glow — top center */}
          <div aria-hidden="true" style={{
            position: 'absolute', top: '-80px', left: '50%', transform: 'translateX(-50%)',
            width: '560px', height: '560px', borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(109,40,217,0.55) 0%, rgba(76,29,149,0.25) 40%, transparent 70%)',
            filter: 'blur(60px)',
            animation: 'moon-glow 8s ease-in-out infinite',
            pointerEvents: 'none',
          }} />

          {/* Horizon glow — left */}
          <div aria-hidden="true" style={{
            position: 'absolute', top: '30%', left: '-8%',
            width: '420px', height: '420px', borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(55,48,163,0.4) 0%, transparent 68%)',
            filter: 'blur(80px)', opacity: 0.6, pointerEvents: 'none',
          }} />

          {/* Horizon glow — right */}
          <div aria-hidden="true" style={{
            position: 'absolute', top: '25%', right: '-5%',
            width: '380px', height: '380px', borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(91,33,182,0.4) 0%, transparent 68%)',
            filter: 'blur(80px)', opacity: 0.55, pointerEvents: 'none',
          }} />

          {/* Moon reflection in the sea */}
          <div aria-hidden="true" style={{
            position: 'absolute', bottom: '15%', left: '50%', transform: 'translateX(-50%)',
            width: '220px', height: '80px', borderRadius: '50%',
            background: 'radial-gradient(ellipse, rgba(139,92,246,0.6) 0%, transparent 70%)',
            filter: 'blur(24px)',
            animation: 'reflection-shimmer 6s ease-in-out infinite',
            pointerEvents: 'none',
          }} />

          {/* Subtle grid */}
          <div className="lp-grid" aria-hidden="true" />

          {/* Floating sea particles */}
          {particles.map((p, i) => (
            <div key={i} aria-hidden="true" className="lp-node" style={{
              top: p.top, left: p.left,
              width: p.size, height: p.size,
              animation: `sea-particle ${p.dur} ease-in-out ${p.delay} infinite`,
            }} />
          ))}

          {/* Hero text */}
          <div className="lp-hero-inner">
            <div className="lp-eyebrow">
              <span className="lp-badge">Open Source</span>
              Local-first AI companion
            </div>
            <h1 className="lp-h1">
              The AI that<br />
              <span className="lp-gradient-text">knows you.</span>
            </h1>
            <p className="lp-subheading">
              L.U.N.A. runs entirely on your machine. Voice, memory, vision,
              and desktop automation — with zero cloud dependency.
            </p>
            <div className="lp-hero-stats" aria-hidden="true">
              <span className="lp-stat"><span className="lp-stat-dot" />Open Source</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Local Inference</span>
              <span className="lp-stat"><span className="lp-stat-dot" />Electron + React</span>
              <span className="lp-stat"><span className="lp-stat-dot" />FastAPI Backend</span>
            </div>
            <div className="lp-hero-actions">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-primary">
                <GitHubIcon />View on GitHub
              </a>
              <Link href="/getting-started" className="lp-btn lp-btn-outline">
                Read the Docs →
              </Link>
            </div>
          </div>

          {/* ── Animated Sea ── */}
          <div aria-hidden="true" style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            height: '42%', overflow: 'hidden', pointerEvents: 'none',
          }}>
            {/* Wave 3 — surface shimmer (fast) */}
            <svg
              style={{ position: 'absolute', bottom: '52%', width: '200%', height: '60px', animation: 'wave-drift-fwd 7s linear infinite' }}
              viewBox="0 0 2880 60" preserveAspectRatio="none"
            >
              <path
                d="M0,30 C240,50 480,10 720,30 C960,50 1200,10 1440,30 C1680,50 1920,10 2160,30 C2400,50 2640,10 2880,30 L2880,60 L0,60 Z"
                fill="rgba(139,92,246,0.18)"
              />
            </svg>

            {/* Wave 2 — mid (medium) */}
            <svg
              style={{ position: 'absolute', bottom: '30%', width: '200%', height: '80px', animation: 'wave-drift-rev 11s linear infinite' }}
              viewBox="0 0 2880 80" preserveAspectRatio="none"
            >
              <path
                d="M0,40 C360,70 720,10 1080,40 C1440,70 1800,10 2160,40 C2520,70 2880,10 2880,40 L2880,80 L0,80 Z"
                fill="rgba(109,40,217,0.32)"
              />
            </svg>

            {/* Wave 1 — deep (slow, opaque) */}
            <svg
              style={{ position: 'absolute', bottom: 0, width: '200%', height: '110px', animation: 'wave-drift-fwd 16s linear infinite' }}
              viewBox="0 0 2880 110" preserveAspectRatio="none"
            >
              <path
                d="M0,55 C480,10 960,100 1440,55 C1920,10 2400,100 2880,55 L2880,110 L0,110 Z"
                fill="rgba(76,29,149,0.55)"
              />
            </svg>

            {/* Sea fill */}
            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0, height: '40%',
              background: 'linear-gradient(to bottom, transparent, rgba(55,20,120,0.45))',
            }} />
          </div>

        </section>

        {/* ── Features ── */}
        <section className="lp-section">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Capabilities</p>
            <h2 className="lp-section-h2">Everything you need from an AI.</h2>
            <p className="lp-section-sub">No subscriptions. No data harvesting. Just intelligence, locally.</p>
            <div className="lp-features-grid">
              {features.map((f) => (
                <div key={f.title} className="lp-feature-card">
                  <div className="lp-feature-icon" aria-hidden="true">{f.icon}</div>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="lp-section">
          <div className="lp-section-inner">
            <p className="lp-eyebrow-label">Workflow</p>
            <h2 className="lp-section-h2">How L.U.N.A. works.</h2>
            <p className="lp-section-sub">Four stages, entirely on your machine.</p>
            <div className="lp-steps-grid">
              {steps.map((s, i) => (
                <div key={i} className="lp-step-card">
                  <div className="lp-step-num" aria-hidden="true">{i + 1}</div>
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '48px' }}>
              <Link href="/workflow" className="lp-btn lp-btn-outline" style={{ display: 'inline-flex' }}>
                See full workflow →
              </Link>
            </div>
          </div>
        </section>

        {/* ── OSS CTA ── */}
        <section className="lp-oss">
          <div className="lp-oss-inner">
            <h2>Built in the open.</h2>
            <p>Free, open-source, and always will be. Inspect every line, fork it, or contribute.</p>
            <div className="lp-oss-actions">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-primary">
                <GitHubIcon />Star on GitHub
              </a>
              <a href="https://www.linkedin.com/in/sehastrajit-s/" target="_blank" rel="noopener noreferrer" className="lp-btn lp-btn-ghost">
                <LinkedInIcon />Connect
              </a>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="lp-footer">
          <div className="lp-footer-inner">
            <div className="lp-footer-brand">
              <img src="/images/logo.svg" alt="" width={22} height={22} />
              <div className="lp-footer-brand-text">
                <span className="lp-footer-name">L.U.N.A.</span>
                <span className="lp-footer-tagline">Large Unified Nexus Mind AI</span>
              </div>
            </div>
            <nav className="lp-footer-links">
              <a href="https://github.com/Sehastrajit/Luna" target="_blank" rel="noopener noreferrer">GitHub</a>
              <a href="https://www.linkedin.com/in/sehastrajit-s/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
              <Link href="/workflow">Workflow</Link>
              <Link href="/getting-started">Docs</Link>
              <Link href="/architecture">Architecture</Link>
            </nav>
          </div>
        </footer>

      </div>
    </>
  );
}
