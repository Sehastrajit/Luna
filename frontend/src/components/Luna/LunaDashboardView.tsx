import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ChevronLeft, ChevronRight, Wind, Droplets } from 'lucide-react'
import { useStore } from '../../store'
import { VoiceOrb } from '../Voice/VoiceOrb'
import { acquireCameraStream } from '../../services/cameraStream'
import { asArray, fetchLuna, fetchLunaCached } from './lunaDashboardApi'

const P = {
  border:      '#1e1e2e',
  borderBright:'rgba(139,92,246,0.42)',
  bg:          'rgba(17,17,24,0.72)',
  surface:     'rgba(17,17,24,0.92)',
  card:        'rgba(22,22,31,0.88)',
  glow:        'rgba(139,92,246,',
  bright:      'rgba(167,139,250,',
  text:        '#e2e8f0',
  textDim:     '#64748b',
  accent:      '#a78bfa',
  green:       '#4ade80',
  red:         '#f87171',
}

// ── Corner accents ─────────────────────────────────────────────────────────────
function Corners({ color = P.borderBright }: { color?: string }) {
  const s: React.CSSProperties = { position: 'absolute', width: 9, height: 9, zIndex: 2 }
  const b = `1px solid ${color}`
  return (
    <>
      <div style={{ ...s, top: 0,    left: 0,  borderTop: b,    borderLeft: b  }} />
      <div style={{ ...s, top: 0,    right: 0, borderTop: b,    borderRight: b }} />
      <div style={{ ...s, bottom: 0, left: 0,  borderBottom: b, borderLeft: b  }} />
      <div style={{ ...s, bottom: 0, right: 0, borderBottom: b, borderRight: b }} />
    </>
  )
}

// ── Expandable HUD panel ───────────────────────────────────────────────────────
function HUDPanel({
  id, title, children, style, headerRight, expanded, onExpand,
}: {
  id: string
  title: string
  children: React.ReactNode
  style?: React.CSSProperties
  headerRight?: React.ReactNode
  expanded: boolean
  onExpand: (id: string | null) => void
}) {
  return (
    <div style={{ border: `1px solid ${expanded ? P.borderBright : P.border}`, background: P.bg, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative', transition: 'border-color 0.25s', ...style }}>
      <Corners color={expanded ? P.borderBright : P.border} />

      {/* Full-width clickable title bar */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onExpand(expanded ? null : id)}
        onKeyDown={e => e.key === 'Enter' && onExpand(expanded ? null : id)}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 10px', borderBottom: `1px solid ${P.border}`, background: expanded ? 'rgba(139,92,246,0.1)' : 'transparent', cursor: 'pointer', flexShrink: 0, userSelect: 'none', transition: 'background 0.2s', outline: 'none' }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.09)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = expanded ? 'rgba(139,92,246,0.1)' : 'transparent')}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.28em', textTransform: 'uppercase', color: expanded ? P.text : P.textDim, pointerEvents: 'none' }}>
          {title}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div onClick={e => e.stopPropagation()}>{headerRight}</div>
          <span style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, opacity: 0.7, pointerEvents: 'none' }}>
            {expanded ? '▼' : '▲'}
          </span>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>{children}</div>
    </div>
  )
}

// ── Full-screen expanded overlay ───────────────────────────────────────────────
function ExpandedOverlay({ title, onClose, children, headerRight }: { title: string; onClose: () => void; children: React.ReactNode; headerRight?: React.ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  return (
    <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      style={{ position: 'absolute', inset: 0, zIndex: 50, display: 'flex', flexDirection: 'column', background: 'rgba(1,0,8,0.98)', border: `1px solid ${P.borderBright}`, backdropFilter: 'blur(12px)' }}>
      <Corners color={P.borderBright} />
      {/* Clicking the title bar again collapses back */}
      <div
        role="button" tabIndex={0}
        onClick={onClose}
        onKeyDown={e => e.key === 'Enter' && onClose()}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 14px', borderBottom: `1px solid ${P.border}`, flexShrink: 0, cursor: 'pointer', userSelect: 'none', transition: 'background 0.15s' }}
        onMouseEnter={e => ((e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.07)')}
        onMouseLeave={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
      >
        <span style={{ fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.3em', textTransform: 'uppercase', color: P.text }}>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }} onClick={e => e.stopPropagation()}>
          {headerRight}
          <button onClick={onClose}
            style={{ background: 'none', border: `1px solid ${P.border}`, cursor: 'pointer', color: P.textDim, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 22, height: 22, transition: 'all 0.15s' }}
            onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.text; el.style.borderColor = `${P.glow}0.5)` }}
            onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.textDim; el.style.borderColor = P.border }}>
            <X size={11} strokeWidth={1.5} />
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>{children}</div>
    </motion.div>
  )
}

// ── Live clock ─────────────────────────────────────────────────────────────────
function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    <div style={{ textAlign: 'right', fontFamily: 'monospace', lineHeight: 1.3 }}>
      <div style={{ fontSize: 15, letterSpacing: '0.1em', color: P.text }}>{pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}</div>
      <div style={{ fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: P.textDim, marginTop: 1 }}>{now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</div>
    </div>
  )
}

// ── News ───────────────────────────────────────────────────────────────────────
interface NewsItem { source: string; title: string; link: string; image?: string; provider?: string }
interface ArticleData { title: string; body: string; image?: string; url: string }

function ArticleReader({ article, onClose }: { article: ArticleData; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.18 }}
      style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div onClick={e => e.stopPropagation()} style={{ width: '72vw', maxWidth: 820, maxHeight: '82vh', background: 'rgba(10,10,18,0.97)', border: `1px solid ${P.borderBright}`, borderRadius: 8, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <Corners />
        {/* Header */}
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${P.border}`, display: 'flex', alignItems: 'flex-start', gap: 10, flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.15em', marginBottom: 6 }}>ARTICLE</div>
            <div style={{ fontSize: 13, color: P.text, lineHeight: 1.4, fontWeight: 500 }}>{article.title || 'Article'}</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
            <button onClick={() => (window as any).electronAPI?.openUrl?.(article.url) ?? window.open(article.url, '_blank')}
              style={{ background: 'none', border: `1px solid ${P.border}`, borderRadius: 4, padding: '3px 8px', cursor: 'pointer', color: P.textDim, fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.08em' }}>
              OPEN
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: P.textDim, display: 'flex', padding: 2 }}><X size={14} /></button>
          </div>
        </div>
        {/* Hero image */}
        {article.image && (
          <div style={{ width: '100%', height: 200, flexShrink: 0, overflow: 'hidden', background: '#0a0a12' }}>
            <img src={article.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', opacity: 0.9 }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
          </div>
        )}
        {/* Body */}
        <div style={{ overflowY: 'auto', padding: '14px 18px', scrollbarWidth: 'none', flex: 1 }}>
          {article.body.split('\n\n').map((para, i) => (
            <p key={i} style={{ fontSize: 12, color: 'rgba(226,232,240,0.82)', lineHeight: 1.7, marginBottom: 12 }}>{para}</p>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function NewsList({ limit }: { limit?: number }) {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [article, setArticle] = useState<ArticleData | null>(null)
  const [fetching, setFetching] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<unknown>('/api/luna/news', 4 * 60_000)
        setItems(asArray<NewsItem>(d))
      } catch (e) {
        console.warn('[luna] news unavailable', e)
        setItems([])
      }
      setLoading(false)
    }
    load()
    const t = setInterval(load, 4 * 60_000)
    return () => clearInterval(t)
  }, [])

  const openArticle = async (item: NewsItem) => {
    if (!item.link || fetching) return
    setFetching(item.link)
    try {
      const d = await fetchLuna<ArticleData>(`/api/luna/article?url=${encodeURIComponent(item.link)}`)
      setArticle(d)
    } catch {
      setArticle({ title: item.title, body: 'Could not load article content.', url: item.link })
    }
    setFetching(null)
  }

  const list = limit ? items.slice(0, limit) : items

  if (loading) return <div style={{ padding: 14, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>loading...</div>
  if (!list.length) return <div style={{ padding: 14, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>no feed</div>

  return (
    <>
      <AnimatePresence>
        {article && <ArticleReader article={article} onClose={() => setArticle(null)} />}
      </AnimatePresence>
      <div style={{ overflowY: 'auto', height: '100%', scrollbarWidth: 'none' }}>
        {list.map((item, i) => (
          <div key={i} role="button" tabIndex={0}
            onClick={() => openArticle(item)}
            style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '7px 10px', background: fetching === item.link ? 'rgba(139,92,246,0.11)' : 'transparent', borderBottom: `1px solid rgba(139,92,246,0.07)`, cursor: 'pointer', transition: 'background 0.12s' }}
            onMouseEnter={e => { if (fetching !== item.link) (e.currentTarget as HTMLElement).style.background = 'rgba(139,92,246,0.07)' }}
            onMouseLeave={e => { if (fetching !== item.link) (e.currentTarget as HTMLElement).style.background = 'transparent' }}>
            {item.image && (
              <img src={item.image} alt="" style={{ width: 52, height: 38, objectFit: 'cover', borderRadius: 3, flexShrink: 0, opacity: 0.88 }} onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 9, color: P.textDim, fontFamily: 'monospace', marginBottom: 3, letterSpacing: '0.1em' }}>
                {item.source.toUpperCase()}{fetching === item.link ? ' — LOADING...' : ''}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.72)', lineHeight: 1.45 }}>{item.title}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ── YouTube ────────────────────────────────────────────────────────────────────
const YT_CHANNELS = [
  { label: 'Al Jazeera', base: 'https://www.youtube.com/embed/jbQC22aDkno?autoplay=1&rel=0&modestbranding=1' },
  { label: 'DW News',    base: 'https://www.youtube.com/embed/live_stream?channel=UCknLrEdhRCp1aegoMqRaCZg&autoplay=1&rel=0&modestbranding=1' },
  { label: 'Reuters TV', base: 'https://www.youtube.com/embed/live_stream?channel=UChqUTb7kYRX8-EiaN3XFrSQ&autoplay=1&rel=0&modestbranding=1' },
  { label: 'France 24',  base: 'https://www.youtube.com/embed/live_stream?channel=UCQfwfsi5VrQ8yKZ-UGuJ7zA&autoplay=1&rel=0&modestbranding=1' },
]

function YoutubeIframe({ idx, muted }: { idx: number; muted: boolean }) {
  const src = `${YT_CHANNELS[idx].base}&mute=${muted ? 1 : 0}`
  return <iframe key={src} src={src} loading="lazy" style={{ width: '100%', height: '100%', border: 'none', display: 'block' }} allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen />
}

function ChannelSwitcher({ idx, setIdx }: { idx: number; setIdx: (i: number) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <button onClick={e => { e.stopPropagation(); setIdx((idx - 1 + YT_CHANNELS.length) % YT_CHANNELS.length) }}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: P.textDim, display: 'flex', padding: '0 2px' }}>
        <ChevronLeft size={11} />
      </button>
      <span style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim, whiteSpace: 'nowrap' }}>{YT_CHANNELS[idx].label}</span>
      <button onClick={e => { e.stopPropagation(); setIdx((idx + 1) % YT_CHANNELS.length) }}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: P.textDim, display: 'flex', padding: '0 2px' }}>
        <ChevronRight size={11} />
      </button>
    </div>
  )
}

// ── Camera with face keypoint overlay ─────────────────────────────────────────
function CameraFeed() {
  const videoRef   = useRef<HTMLVideoElement>(null)
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const detectorRef = useRef<any>(null)
  const [state, setState] = useState<'loading' | 'active' | 'error'>('loading')

  // Init FaceDetector (Chrome Shape Detection API, available in Electron/Chromium)
  useEffect(() => {
    try {
      detectorRef.current = new (window as any).FaceDetector({ maxDetectedFaces: 1, fastMode: true })
    } catch { /* not available, canvas stays blank */ }
  }, [])

  // Attach camera stream
  useEffect(() => {
    let cancelled = false
    acquireCameraStream().then(stream => {
      if (cancelled) return
      if (!stream) { setState('error'); return }
      if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play().catch(() => {}) }
      setState('active')
    })
    return () => { cancelled = true }
  }, [])

  // Face detection loop — runs at ~5 fps
  useEffect(() => {
    if (state !== 'active') return
    let stopped = false

    const tick = async () => {
      if (stopped) return
      const video    = videoRef.current
      const canvas   = canvasRef.current
      const detector = detectorRef.current
      if (video && canvas && detector && video.readyState >= 2) {
        const vw = video.videoWidth  || 640
        const vh = video.videoHeight || 480
        if (canvas.width !== vw)  canvas.width  = vw
        if (canvas.height !== vh) canvas.height = vh

        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.clearRect(0, 0, vw, vh)
          try {
            const faces: any[] = await detector.detect(video)
            for (const face of faces) {
              const { x, y, width, height } = face.boundingBox
              // corner brackets instead of a full rectangle
              const cs = Math.min(14, width * 0.18)
              ctx.strokeStyle = 'rgba(167,139,250,0.85)'
              ctx.lineWidth   = 1.5
              const corners = [
                [[x,       y+cs], [x,       y], [x+cs,       y]],
                [[x+width-cs, y], [x+width, y], [x+width, y+cs]],
                [[x,       y+height-cs], [x, y+height], [x+cs, y+height]],
                [[x+width-cs, y+height], [x+width, y+height], [x+width, y+height-cs]],
              ] as [number,number][][]
              for (const pts of corners) {
                ctx.beginPath()
                ctx.moveTo(pts[0][0], pts[0][1])
                ctx.lineTo(pts[1][0], pts[1][1])
                ctx.lineTo(pts[2][0], pts[2][1])
                ctx.stroke()
              }
              // landmarks (eyes, nose, mouth)
              for (const lm of face.landmarks ?? []) {
                const lx = lm.location?.x ?? lm.x ?? 0
                const ly = lm.location?.y ?? lm.y ?? 0
                const grad = ctx.createRadialGradient(lx, ly, 0, lx, ly, 5)
                grad.addColorStop(0, 'rgba(167,139,250,1)')
                grad.addColorStop(1, 'rgba(139,92,246,0)')
                ctx.beginPath()
                ctx.arc(lx, ly, 5, 0, Math.PI * 2)
                ctx.fillStyle = grad
                ctx.fill()
                ctx.beginPath()
                ctx.arc(lx, ly, 2, 0, Math.PI * 2)
                ctx.fillStyle = 'rgba(216,180,254,0.95)'
                ctx.fill()
              }
            }
          } catch { /* ignore per-frame errors */ }
        }
      }
      if (!stopped) setTimeout(tick, 200)
    }

    tick()
    return () => { stopped = true }
  }, [state])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#000', overflow: 'hidden' }}>
      {state !== 'active' && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.15em' }}>
          {state === 'loading' ? 'CONNECTING...' : 'NO SIGNAL'}
        </div>
      )}
      <video ref={videoRef} autoPlay muted playsInline
        style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', display: state === 'active' ? 'block' : 'none' }} />
      {/* Canvas mirrors video CSS transform so FaceDetector raw coords align visually */}
      <canvas ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', transform: 'scaleX(-1)', pointerEvents: 'none', display: state === 'active' ? 'block' : 'none' }} />
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px)', mixBlendMode: 'overlay' }} />
    </div>
  )
}

// ── Stocks ────────────────────────────────────────────────────────────────────
interface StockItem { symbol: string; price: number; pct: number; change?: number; source?: string; stale?: boolean; date?: string }
interface StockPoint { date: string; price: number }
interface StockHistory { symbol: string; source: string; points: StockPoint[]; high: number; low: number; open: number; close: number }

function fmtPrice(sym: string, price: number) {
  if (['BTC','ETH'].includes(sym)) return price >= 1000 ? `$${(price/1000).toFixed(1)}k` : `$${price.toFixed(0)}`
  return `$${price.toFixed(2)}`
}

function StockChart({ points, positive }: { points: StockPoint[]; positive: boolean }) {
  const width = 360
  const height = 112
  const prices = points.map(p => p.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const span = max - min || 1
  const d = points.map((p, i) => {
    const x = points.length === 1 ? 0 : (i / (points.length - 1)) * width
    const y = height - ((p.price - min) / span) * height
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  const stroke = positive ? P.green : P.red

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: 112, display: 'block' }}>
      <path d={`M0,${height} ${d.replace(/^M/, 'L')} L${width},${height} Z`} fill={positive ? 'rgba(74,222,128,0.08)' : 'rgba(248,113,113,0.08)'} />
      <path d={d} fill="none" stroke={stroke} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function StockDetails({ stock }: { stock: StockItem }) {
  const [history, setHistory] = useState<StockHistory | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setHistory(null)
    fetchLunaCached<StockHistory>(`/api/luna/stocks/${stock.symbol}/history`, 5 * 60_000)
      .then(d => { if (!cancelled) { setHistory(d); setStatus('ok') } })
      .catch(e => { console.warn('[luna] stock history unavailable', e); if (!cancelled) setStatus('error') })
    return () => { cancelled = true }
  }, [stock.symbol])

  const positive = stock.pct >= 0
  return (
    <div style={{ borderBottom: `1px solid ${P.border}`, background: P.card, padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ fontFamily: 'monospace', fontSize: 18, color: P.text, letterSpacing: '0.08em' }}>{stock.symbol}</div>
          <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>{stock.source ?? (['BTC','ETH'].includes(stock.symbol) ? 'Crypto' : 'Equity')}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'monospace', fontSize: 18, color: P.text }}>{fmtPrice(stock.symbol, stock.price)}</div>
          <div style={{ fontFamily: 'monospace', fontSize: 11, color: positive ? P.green : P.red }}>{positive ? '+' : ''}{stock.pct.toFixed(2)}%</div>
        </div>
      </div>
      {status === 'loading' && <div style={{ height: 112, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>LOADING GRAPH...</div>}
      {status === 'error' && <div style={{ height: 112, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>GRAPH UNAVAILABLE</div>}
      {history && (
        <>
          <StockChart points={history.points} positive={history.close >= history.open} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 10 }}>
            {[
              ['OPEN', fmtPrice(stock.symbol, history.open)],
              ['CLOSE', fmtPrice(stock.symbol, history.close)],
              ['HIGH', fmtPrice(stock.symbol, history.high)],
              ['LOW', fmtPrice(stock.symbol, history.low)],
            ].map(([label, value]) => (
              <div key={label} style={{ border: `1px solid ${P.border}`, padding: '6px 7px', background: 'rgba(9,9,15,0.45)' }}>
                <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.16em' }}>{label}</div>
                <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.text, marginTop: 2 }}>{value}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function StocksList({ large }: { large?: boolean }) {
  const [stocks, setStocks] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<StockItem | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<unknown>('/api/luna/stocks', 90_000)
        setStocks(asArray<StockItem>(d))
      } catch (e) {
        console.warn('[luna] market unavailable', e)
        setStocks([])
      }
      setLoading(false)
    }
    load()
    const t = setInterval(load, 90_000)
    return () => clearInterval(t)
  }, [])

  if (loading) return <div style={{ padding: 12, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>loading...</div>
  if (!stocks.length) return <div style={{ padding: 12, color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>unavailable</div>

  return (
    <div style={{ overflowY: 'auto', height: '100%', scrollbarWidth: 'none' }}>
      {selected && <StockDetails stock={selected} />}
      {stocks.some(s => s.stale) && (
        <div style={{ padding: '3px 10px', fontSize: 9, fontFamily: 'monospace', color: '#facc15', letterSpacing: '0.08em', borderBottom: `1px solid rgba(139,92,246,0.07)` }}>
          PREV CLOSE — markets closed
        </div>
      )}
      {stocks.map((s, i) => (
        <div key={i} role="button" tabIndex={0} onClick={() => setSelected(s)} onKeyDown={e => e.key === 'Enter' && setSelected(s)} style={{ display: 'grid', gridTemplateColumns: '52px 1fr auto', alignItems: 'center', padding: large ? '10px 14px' : '6px 10px', borderBottom: `1px solid rgba(139,92,246,0.07)`, gap: 8, cursor: 'pointer', background: selected?.symbol === s.symbol ? 'rgba(139,92,246,0.11)' : 'transparent', opacity: s.stale ? 0.75 : 1 }}>
          <span style={{ fontFamily: 'monospace', fontSize: large ? 13 : 11, color: P.text, fontWeight: 500 }}>{s.symbol}</span>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontFamily: 'monospace', fontSize: large ? 12 : 11, color: 'rgba(255,255,255,0.58)' }}>{fmtPrice(s.symbol, s.price)}</span>
            {s.stale && s.date && <span style={{ fontFamily: 'monospace', fontSize: 8, color: '#facc1580', letterSpacing: '0.05em' }}>{s.date}</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <span style={{ fontFamily: 'monospace', fontSize: large ? 11 : 10, color: s.pct >= 0 ? P.green : P.red, whiteSpace: 'nowrap' }}>
              {s.pct >= 0 ? '+' : ''}{s.pct.toFixed(2)}%
            </span>
            {large && s.pct !== 0 && (
              <div style={{ width: 48, height: 2, marginTop: 3, background: 'rgba(255,255,255,0.08)', borderRadius: 1, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, Math.abs(s.pct) * 20)}%`, height: '100%', background: s.pct >= 0 ? P.green : P.red, borderRadius: 1 }} />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Weather widget ─────────────────────────────────────────────────────────────
interface Weather { temp_f: number; feels_f: number; humidity: number; wind_mph: number; condition: string; city: string; source?: string }

function WeatherWidget() {
  const [wx, setWx]       = useState<Weather | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLunaCached<Weather | null>('/api/luna/weather', 10 * 60_000)
        if (d?.temp_f !== undefined) { setWx(d); setStatus('ok') }
        else setStatus('error')
      } catch (e) {
        console.warn('[luna] weather unavailable', e)
        setStatus('error')
      }
    }
    load()
    const t = setInterval(load, 10 * 60_000)
    return () => clearInterval(t)
  }, [])

  if (status !== 'ok' || !wx) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: P.textDim, fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.1em' }}>
      {status === 'loading' ? 'FETCHING...' : 'UNAVAILABLE'}
    </div>
  )

  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 5, height: '100%', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'monospace', fontSize: 34, color: P.text, fontWeight: 200, letterSpacing: '-0.02em' }}>{wx.temp_f}°</span>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>F</span>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim, marginLeft: 4 }}>{wx.city}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'rgba(255,255,255,0.65)' }}>{wx.condition}</div>
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: 9, color: P.textDim }}><Droplets size={9} />{wx.humidity}%</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'monospace', fontSize: 9, color: P.textDim }}><Wind size={9} />{wx.wind_mph} mph</div>
        <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim }}>feels {wx.feels_f}°</div>
      </div>
    </div>
  )
}

// ── Awareness (vision context) ─────────────────────────────────────────────────
interface VisionCtx { active: boolean; emotion?: string; posture?: string; energy?: string; environment?: string; activity?: string; captured_at?: number }

function AwarenessWidget() {
  const [ctx, setCtx]     = useState<VisionCtx | null>(null)
  const [status, setStatus] = useState<'loading' | 'ok' | 'idle'>('loading')

  useEffect(() => {
    const load = async () => {
      try {
        const d = await fetchLuna<VisionCtx>('/api/vision/context')
        setCtx(d)
        setStatus(d.active ? 'ok' : 'idle')
      } catch { setStatus('idle') }
    }
    load()
    const t = setInterval(load, 12_000)
    return () => clearInterval(t)
  }, [])

  const row = (label: string, val?: string) => val && val.toLowerCase() !== 'unclear' ? (
    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
      <span style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.18em', flexShrink: 0, width: 56 }}>{label}</span>
      <span style={{ fontFamily: 'monospace', fontSize: 10, color: 'rgba(255,255,255,0.72)', lineHeight: 1.3 }}>{val}</span>
    </div>
  ) : null

  if (status === 'loading') return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>WAITING...</div>

  if (!ctx?.active) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 5 }}>
      <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>NO SIGNAL</span>
      <span style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.5)', textAlign: 'center', maxWidth: 140, lineHeight: 1.5 }}>camera frames sent to moondream every 30s</span>
    </div>
  )

  const age = ctx.captured_at ? Math.round((Date.now() / 1000) - ctx.captured_at) : null

  return (
    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6, height: '100%', justifyContent: 'center' }}>
      {row('EMOTION',  ctx.emotion)}
      {row('POSTURE',  ctx.posture)}
      {row('ENERGY',   ctx.energy)}
      {row('ACTIVITY', ctx.activity)}
      {row('SETTING',  ctx.environment)}
      {age !== null && (
        <div style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.5)', marginTop: 2 }}>
          updated {age < 60 ? `${age}s` : `${Math.round(age/60)}m`} ago
        </div>
      )}
    </div>
  )
}

// ── Orb rings ──────────────────────────────────────────────────────────────────
function OrbCluster() {
  const rings = [
    { size: 244, dur: 28, rev: false, op: 0.14, bT: `${P.bright}0.5)`,  bR: `${P.glow}0.06)` },
    { size: 192, dur: 16, rev: true,  op: 0.22, bT: `${P.bright}0.72)`, bB: `${P.bright}0.5)`, bL: `${P.glow}0.08)`, bR: `${P.glow}0.08)` },
    { size: 138, dur: 9,  rev: false, op: 0.32, bT: `${P.bright}0.85)`, bR: `${P.bright}0.6)`, bB: `${P.glow}0.12)`, bL: `${P.glow}0.12)`, bW: 1.5 },
  ]
  return (
    <div style={{ position: 'relative', width: 248, height: 248, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      {rings.map((ring, i) => (
        <motion.div key={i} style={{ position: 'absolute', width: ring.size, height: ring.size, borderRadius: '50%', border: `${ring.bW ?? 1}px solid ${P.glow}${ring.op})`, borderTopColor: ring.bT, borderRightColor: ring.bR ?? `${P.glow}${ring.op})`, borderBottomColor: (ring as any).bB ?? `${P.glow}${ring.op})`, borderLeftColor: (ring as any).bL ?? `${P.glow}${ring.op})` }} animate={{ rotate: ring.rev ? -360 : 360 }} transition={{ duration: ring.dur, repeat: Infinity, ease: 'linear' }} />
      ))}
      <motion.div style={{ position: 'absolute', width: 112, height: 112, borderRadius: '50%', border: `1px solid ${P.glow}0.28)` }} animate={{ scale: [1, 1.65], opacity: [0.45, 0] }} transition={{ duration: 3, repeat: Infinity, ease: 'easeOut' }} />
      <div style={{ position: 'relative', zIndex: 5 }}><VoiceOrb size={88} /></div>
    </div>
  )
}

// ── Messages ───────────────────────────────────────────────────────────────────
function LunaMessages() {
  const { messages, isStreaming, streamingContent } = useStore(s => ({ messages: s.messages, isStreaming: s.isStreaming, streamingContent: s.streamingContent }))
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages.length, streamingContent])

  return (
    <div style={{ width: '100%', maxHeight: '22vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, scrollbarWidth: 'none' }}>
      <AnimatePresence initial={false}>
        {messages.slice(-7).map(m => (
          <motion.div key={m.id} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
            style={{ fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5, color: m.role === 'user' ? 'rgba(255,255,255,0.42)' : P.text, textAlign: m.role === 'user' ? 'right' : 'left', padding: '3px 0', borderBottom: `1px solid ${P.border}` }}>
            {m.role === 'assistant' && <span style={{ color: P.textDim, marginRight: 6, fontSize: 9 }}>LUNA</span>}
            {m.content}
          </motion.div>
        ))}
      </AnimatePresence>
      {isStreaming && streamingContent && (
        <div style={{ fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5, color: P.text, padding: '3px 0' }}>
          <span style={{ color: P.textDim, marginRight: 6, fontSize: 9 }}>LUNA</span>
          {streamingContent}
          <motion.span animate={{ opacity: [1, 0] }} transition={{ duration: 0.7, repeat: Infinity }}>▊</motion.span>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}

// ── Template switcher ──────────────────────────────────────────────────────────
type WidgetTemplate = 'standard' | 'broadcast'

function WidgetTemplateSwitcher({ template, setTemplate }: { template: WidgetTemplate; setTemplate: (t: WidgetTemplate) => void }) {
  const opts: { id: WidgetTemplate; label: string }[] = [
    { id: 'standard',  label: 'STANDARD' },
    { id: 'broadcast', label: 'BROADCAST' },
  ]
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {opts.map(o => (
        <button key={o.id} onClick={() => setTemplate(o.id)}
          style={{ background: template === o.id ? 'rgba(139,92,246,0.18)' : 'transparent', border: `1px solid ${template === o.id ? P.borderBright : P.border}`, cursor: 'pointer', color: template === o.id ? P.text : P.textDim, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.22em', padding: '3px 8px', transition: 'all 0.15s' }}
          onMouseEnter={e => { if (template !== o.id) { (e.currentTarget as HTMLElement).style.borderColor = P.borderBright; (e.currentTarget as HTMLElement).style.color = P.text } }}
          onMouseLeave={e => { if (template !== o.id) { (e.currentTarget as HTMLElement).style.borderColor = P.border; (e.currentTarget as HTMLElement).style.color = P.textDim } }}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

const EXPANDED_TITLES: Record<string, string> = { youtube: 'LIVE NEWS', market: 'MARKET', news: 'NEWS FEED', camera: 'CAMERA', weather: 'WEATHER' }

function BroadcastTemplate({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ height: '100%', display: 'grid', gridTemplateRows: 'auto 1fr', background: P.surface }}>
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${P.border}`, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.34em', color: P.accent }}>{title}</span>
        <span style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim, letterSpacing: '0.2em' }}>BROADCAST TEMPLATE</span>
      </div>
      <div style={{ minHeight: 0, padding: 12 }}>{children}</div>
    </div>
  )
}

function ExpandedContent({ id, ytIdx, template }: { id: string; ytIdx: number; setYtIdx: (i: number) => void; template: WidgetTemplate }) {
  const content =
    id === 'youtube' ? <YoutubeIframe idx={ytIdx} muted={false} /> :
    id === 'market'  ? <StocksList large /> :
    id === 'news'    ? <NewsList /> :
    id === 'camera'  ? <CameraFeed /> :
    id === 'weather' ? <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}><WeatherWidget /></div> :
    null

  if (!content) return null
  if (template === 'broadcast') return <BroadcastTemplate title={EXPANDED_TITLES[id] ?? id.toUpperCase()}>{content}</BroadcastTemplate>
  return content
}

// ── Broadcast layout ───────────────────────────────────────────────────────────
function BroadcastLayout({ expanded, setExpanded, ytIdx, setYtIdx }: { expanded: string | null; setExpanded: (id: string | null) => void; ytIdx: number; setYtIdx: (i: number) => void }) {
  return (
    <div style={{ flex: 1, position: 'relative', display: 'grid', gridTemplateColumns: '1fr 230px', gap: 8, padding: 8, minHeight: 0, overflow: 'hidden', WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
      {/* Ambient orb — behind panels */}
      <div style={{ position: 'absolute', top: '50%', left: '38%', transform: 'translate(-50%,-50%)', opacity: 0.2, pointerEvents: 'none', zIndex: 0 }}>
        <OrbCluster />
      </div>
      <HUDPanel id="youtube" title="LIVE NEWS" expanded={expanded === 'youtube'} onExpand={setExpanded} style={{ zIndex: 1 }} headerRight={<ChannelSwitcher idx={ytIdx} setIdx={setYtIdx} />}>
        <YoutubeIframe idx={ytIdx} muted={false} />
      </HUDPanel>
      <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 8, minHeight: 0, zIndex: 1 }}>
        <HUDPanel id="market" title="MARKET" expanded={expanded === 'market'} onExpand={setExpanded}><StocksList /></HUDPanel>
        <HUDPanel id="news"   title="NEWS FEED" expanded={expanded === 'news'} onExpand={setExpanded}><NewsList limit={20} /></HUDPanel>
      </div>
      <AnimatePresence>
        {expanded && (
          <ExpandedOverlay key={expanded} title={EXPANDED_TITLES[expanded] ?? expanded} onClose={() => setExpanded(null)} headerRight={expanded === 'youtube' ? <ChannelSwitcher idx={ytIdx} setIdx={setYtIdx} /> : undefined}>
            <ExpandedContent id={expanded} ytIdx={ytIdx} setYtIdx={setYtIdx} template="standard" />
          </ExpandedOverlay>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Default layout ─────────────────────────────────────────────────────────────
interface DashboardBrief {
  weather: Weather | null
  stocks: StockItem[]
  news: NewsItem[]
}

function LunaDataBrief() {
  const [brief, setBrief] = useState<DashboardBrief | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [weather, stocksRaw, newsRaw] = await Promise.all([
          fetchLunaCached<Weather | null>('/api/luna/weather', 10 * 60_000),
          fetchLunaCached<unknown>('/api/luna/stocks', 90_000),
          fetchLunaCached<unknown>('/api/luna/news', 4 * 60_000),
        ])
        setBrief({ weather, stocks: asArray<StockItem>(stocksRaw), news: asArray<NewsItem>(newsRaw) })
      } catch (e) {
        console.warn('[luna] data brief unavailable', e)
      }
    }
    load()
    const t = setInterval(load, 90_000)
    return () => clearInterval(t)
  }, [])

  const lead = brief?.news[0]?.title ?? 'Waiting for live feed data.'
  const movers = brief?.stocks.slice(0, 3).map(s => `${s.symbol} ${s.pct >= 0 ? '+' : ''}${s.pct.toFixed(2)}%`).join('  /  ') || 'Market data loading.'
  const weather = brief?.weather ? `${brief.weather.city}: ${brief.weather.temp_f}F, ${brief.weather.condition}` : 'Weather loading.'

  return (
    <div style={{ padding: '8px 12px', display: 'grid', gap: 5, height: '100%', alignContent: 'center' }}>
      <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.accent, letterSpacing: '0.18em' }}>VISUALIZING</div>
      <div style={{ fontFamily: 'monospace', fontSize: 10, color: P.text, lineHeight: 1.35 }}>{weather}</div>
      <div style={{ fontFamily: 'monospace', fontSize: 9, color: P.textDim, lineHeight: 1.35 }}>{movers}</div>
      <div style={{ fontSize: 10, color: 'rgba(226,232,240,0.68)', lineHeight: 1.35, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{lead}</div>
    </div>
  )
}

function DefaultLayout({ expanded, setExpanded, ytIdx, setYtIdx, widgetTemplate, setWidgetTemplate }: { expanded: string | null; setExpanded: (id: string | null) => void; ytIdx: number; setYtIdx: (i: number) => void; widgetTemplate: WidgetTemplate; setWidgetTemplate: (t: WidgetTemplate) => void }) {
  return (
    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '340px 1fr 340px', gap: 8, padding: 8, minHeight: 0, overflow: 'hidden', position: 'relative', WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
      {/* Left */}
      <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 8, minHeight: 0 }}>
        <HUDPanel id="news" title="NEWS FEED" expanded={expanded === 'news'} onExpand={setExpanded}><NewsList limit={20} /></HUDPanel>
        <HUDPanel id="youtube" title="LIVE NEWS" expanded={expanded === 'youtube'} onExpand={setExpanded} headerRight={<ChannelSwitcher idx={ytIdx} setIdx={setYtIdx} />}>
          <YoutubeIframe idx={ytIdx} muted={expanded !== 'youtube'} />
        </HUDPanel>
      </div>
      {/* Center */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, minHeight: 0, overflow: 'hidden', padding: '6px 8px' }}>
        {/* Data row: Weather + Awareness — top */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, width: '100%', height: 148, flexShrink: 0 }}>
          <div style={{ border: `1px solid ${P.border}`, background: P.bg, position: 'relative', overflow: 'hidden' }}>
            <Corners />
            <div style={{ padding: '4px 8px', borderBottom: `1px solid ${P.border}`, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.25em', color: P.textDim }}>WEATHER</div>
            <WeatherWidget />
          </div>
          <div style={{ border: `1px solid ${P.border}`, background: P.bg, position: 'relative', overflow: 'hidden' }}>
            <Corners />
            <div style={{ padding: '4px 8px', borderBottom: `1px solid ${P.border}`, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.25em', color: P.textDim }}>AWARENESS</div>
            <AwarenessWidget />
          </div>
        </div>
        {/* Orb — centered, takes all remaining flex space */}
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
          <div style={{ transform: 'scale(1.06)', transformOrigin: 'center center' }}>
            <OrbCluster />
          </div>
        </div>
        {/* LUNA messages — fixed compact height at bottom */}
        <div style={{ width: '100%', height: 132, flexShrink: 0, border: `1px solid ${P.border}`, background: P.bg, position: 'relative', overflow: 'hidden' }}>
          <Corners />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', height: '100%' }}>
            <div style={{ minWidth: 0, borderRight: `1px solid ${P.border}` }}>
              <div style={{ padding: '4px 8px', borderBottom: `1px solid ${P.border}`, fontFamily: 'monospace', fontSize: 8, letterSpacing: '0.25em', color: P.textDim }}>LUNA</div>
              <div style={{ height: 'calc(100% - 22px)', overflow: 'hidden' }}>
                <LunaMessages />
              </div>
            </div>
            <div style={{ minWidth: 0 }}>
              <LunaDataBrief />
            </div>
          </div>
        </div>
      </div>
      {/* Right */}
      <div style={{ display: 'grid', gridTemplateRows: '38% 62%', gap: 8, minHeight: 0 }}>
        <HUDPanel id="camera" title="CAMERA" expanded={expanded === 'camera'} onExpand={setExpanded}><CameraFeed /></HUDPanel>
        <HUDPanel id="market" title="MARKET" expanded={expanded === 'market'} onExpand={setExpanded}><StocksList /></HUDPanel>
      </div>
      <AnimatePresence>
        {expanded && (
          <ExpandedOverlay key={expanded} title={EXPANDED_TITLES[expanded] ?? expanded} onClose={() => setExpanded(null)} headerRight={<div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{expanded === 'youtube' && <ChannelSwitcher idx={ytIdx} setIdx={setYtIdx} />}<WidgetTemplateSwitcher template={widgetTemplate} setTemplate={setWidgetTemplate} /></div>}>
            <ExpandedContent id={expanded} ytIdx={ytIdx} setYtIdx={setYtIdx} template={widgetTemplate} />
          </ExpandedOverlay>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main view ──────────────────────────────────────────────────────────────────
export function LunaDashboardView() {
  const exitLunaDashboard = useStore(s => s.exitLunaDashboard)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [widgetTemplate, setWidgetTemplate] = useState<WidgetTemplate>('standard')
  const [ytIdx, setYtIdx]       = useState(0)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !expanded) exitLunaDashboard() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [exitLunaDashboard, expanded])

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.28 }}
      style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', flexDirection: 'column', background: '#09090f', overflow: 'hidden' }}>

      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 44% 36% at 50% 44%, rgba(139,92,246,0.12) 0%, transparent 72%)', pointerEvents: 'none' }} />

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: `1px solid ${P.border}`, background: P.surface, backdropFilter: 'blur(8px)', flexShrink: 0, zIndex: 60, WebkitAppRegion: 'drag' } as React.CSSProperties}>
        <button onClick={exitLunaDashboard} title="Exit (Esc)"
          style={{ background: 'none', border: `1px solid ${P.border}`, cursor: 'pointer', color: P.textDim, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, transition: 'all 0.15s', WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.text; el.style.borderColor = `${P.glow}0.5)` }}
          onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.color = P.textDim; el.style.borderColor = P.border }}>
          <X size={12} strokeWidth={1.5} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          <span style={{ fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.45em', textTransform: 'uppercase', color: P.textDim }}>Luna</span>
        </div>
        <div style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}><LiveClock /></div>
      </div>

      <motion.div key="default" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <DefaultLayout expanded={expanded} setExpanded={setExpanded} ytIdx={ytIdx} setYtIdx={setYtIdx} widgetTemplate={widgetTemplate} setWidgetTemplate={setWidgetTemplate} />
      </motion.div>
    </motion.div>
  )
}
