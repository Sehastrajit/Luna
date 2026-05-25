import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import { acquireCameraStream } from '../../services/cameraStream'

// MediaPipe is loaded as a plain script tag in index.html (UMD global)
const mp = () => (window as any)
type MPResults = { multiFaceLandmarks?: { x: number; y: number; z: number }[][] }

const W = 320
const H = 240

function drawMesh(ctx: CanvasRenderingContext2D, results: MPResults, vw: number, vh: number) {
  ctx.clearRect(0, 0, vw, vh)
  const faces = results.multiFaceLandmarks ?? []
  if (faces.length === 0) return faces.length

  const w = mp()
  const TESS  = w.FACEMESH_TESSELATION  ?? []
  const OVAL  = w.FACEMESH_FACE_OVAL    ?? []
  const L_EYE = w.FACEMESH_LEFT_EYE    ?? []
  const R_EYE = w.FACEMESH_RIGHT_EYE   ?? []
  const LIPS  = w.FACEMESH_LIPS        ?? []

  for (const lms of faces) {
    const lx = (i: number) => lms[i].x * vw
    const ly = (i: number) => lms[i].y * vh

    // ── Full tessellation mesh ─────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(109,40,217,0.22)'
    ctx.lineWidth = 0.55
    for (const [a, b] of TESS) {
      ctx.beginPath(); ctx.moveTo(lx(a), ly(a)); ctx.lineTo(lx(b), ly(b)); ctx.stroke()
    }

    // ── Face oval contour ──────────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(139,92,246,0.7)'
    ctx.lineWidth = 1.2
    for (const [a, b] of OVAL) {
      ctx.beginPath(); ctx.moveTo(lx(a), ly(a)); ctx.lineTo(lx(b), ly(b)); ctx.stroke()
    }

    // ── Eyes ──────────────────────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(196,165,255,0.9)'
    ctx.lineWidth = 1.1
    for (const [a, b] of [...L_EYE, ...R_EYE]) {
      ctx.beginPath(); ctx.moveTo(lx(a), ly(a)); ctx.lineTo(lx(b), ly(b)); ctx.stroke()
    }

    // ── Lips ──────────────────────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(216,180,254,0.75)'
    ctx.lineWidth = 1
    for (const [a, b] of LIPS) {
      ctx.beginPath(); ctx.moveTo(lx(a), ly(a)); ctx.lineTo(lx(b), ly(b)); ctx.stroke()
    }

    // ── Bounding box + corner brackets ────────────────────────────────────
    const xs = lms.map(l => l.x * vw)
    const ys = lms.map(l => l.y * vh)
    const x0 = Math.min(...xs) - 8, y0 = Math.min(...ys) - 10
    const x1 = Math.max(...xs) + 8, y1 = Math.max(...ys) + 10
    const bw = x1 - x0, bh = y1 - y0
    const cs = Math.min(18, bw * 0.18)

    ctx.strokeStyle = 'rgba(216,180,254,0.95)'
    ctx.lineWidth = 2
    ;([[x0, y0, 1, 1], [x1, y0, -1, 1], [x0, y1, 1, -1], [x1, y1, -1, -1]] as const).forEach(([px, py, sx, sy]) => {
      ctx.beginPath()
      ctx.moveTo(px + sx * cs, py); ctx.lineTo(px, py); ctx.lineTo(px, py + sy * cs)
      ctx.stroke()
    })

    // ── Scan line ─────────────────────────────────────────────────────────
    const scanY = y0 + ((Date.now() / 1200) % 1) * bh
    const sg = ctx.createLinearGradient(x0, scanY - 8, x0, scanY + 8)
    sg.addColorStop(0,   'rgba(167,139,250,0)')
    sg.addColorStop(0.5, 'rgba(167,139,250,0.38)')
    sg.addColorStop(1,   'rgba(167,139,250,0)')
    ctx.fillStyle = sg
    ctx.fillRect(x0, scanY - 8, bw, 16)

    // ── Label ─────────────────────────────────────────────────────────────
    ctx.fillStyle = 'rgba(196,165,255,0.8)'
    ctx.font = 'bold 8px monospace'
    ctx.fillText('FACE LOCK', x0 + 2, Math.max(y0 - 4, 8))
  }

  return faces.length
}

export function FaceTrackingPanel() {
  const enabled  = useStore(s => s.faceTrackingEnabled)
  const disable  = useStore(s => s.disableFaceTracking)
  const videoRef  = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const meshRef   = useRef<any>(null)
  const [status, setStatus]     = useState<'init' | 'ready' | 'error'>('init')
  const [faceCount, setFaceCount] = useState(0)

  // Init MediaPipe FaceMesh on mount
  useEffect(() => {
    const FaceMesh = (window as any).FaceMesh
    if (!FaceMesh) { setStatus('error'); return }
    const fm = new FaceMesh({
      locateFile: (file: string) => `/mediapipe/${file}`,
    })
    fm.setOptions({
      maxNumFaces: 1,
      refineLandmarks: false,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
      selfieMode: true,
    })
    fm.onResults((results: MPResults) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const count = drawMesh(ctx, results, canvas.width, canvas.height)
      setFaceCount(count)
    })
    meshRef.current = fm
    fm.initialize()
      .then(() => setStatus('ready'))
      .catch(() => setStatus('error'))
    return () => { fm.close() }
  }, [])

  // Attach camera stream
  useEffect(() => {
    let cancelled = false
    acquireCameraStream().then(stream => {
      if (cancelled) return
      if (!stream) { setStatus('error'); return }
      const v = videoRef.current
      if (v) { v.srcObject = stream; v.play().catch(() => {}) }
    })
    return () => { cancelled = true }
  }, [])

  // Send frames to FaceMesh ~8 fps
  useEffect(() => {
    if (status !== 'ready') return
    let stopped = false

    const tick = async () => {
      if (stopped) return
      const video  = videoRef.current
      const fm     = meshRef.current
      const canvas = canvasRef.current
      if (video && fm && canvas && video.readyState >= 2) {
        const vw = video.videoWidth  || 640
        const vh = video.videoHeight || 480
        if (canvas.width  !== vw) canvas.width  = vw
        if (canvas.height !== vh) canvas.height = vh
        try { await fm.send({ image: video }) } catch { /* ignore */ }
      }
      if (!stopped) setTimeout(tick, 125)
    }
    tick()
    return () => { stopped = true }
  }, [status])

  if (!enabled) return null

  const isActive = status === 'ready'

  return (
    <div style={{
      position: 'relative', width: W, height: H, borderRadius: 6,
      overflow: 'hidden', flexShrink: 0,
      border: '1px solid rgba(139,92,246,0.45)',
      boxShadow: '0 0 28px rgba(139,92,246,0.22)',
      background: '#000',
    }}>
      {/* Status overlay while loading */}
      {!isActive && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 2,
          color: 'rgba(100,116,139,0.65)', fontFamily: 'monospace',
          fontSize: 10, letterSpacing: '0.18em',
        }}>
          {status === 'error' ? 'NO SIGNAL' : 'INITIALIZING...'}
        </div>
      )}

      {/* Live camera feed — CSS-mirrored to match selfieMode landmarks */}
      <video ref={videoRef} autoPlay muted playsInline style={{
        width: '100%', height: '100%', objectFit: 'cover',
        transform: 'scaleX(-1)',
        display: isActive ? 'block' : 'none',
      }} />

      {/* Transparent mesh overlay */}
      <canvas ref={canvasRef} style={{
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        transform: 'scaleX(-1)',
        pointerEvents: 'none',
        display: isActive ? 'block' : 'none',
      }} />

      {/* CRT scanlines */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 1,
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px)',
        mixBlendMode: 'overlay',
      }} />

      {/* HUD corner brackets */}
      <div style={{ position: 'absolute', top: 0, left: 0, width: 14, height: 14, borderTop: '1px solid rgba(139,92,246,0.6)', borderLeft: '1px solid rgba(139,92,246,0.6)', pointerEvents: 'none', zIndex: 3 }} />
      <div style={{ position: 'absolute', top: 0, right: 0, width: 14, height: 14, borderTop: '1px solid rgba(139,92,246,0.6)', borderRight: '1px solid rgba(139,92,246,0.6)', pointerEvents: 'none', zIndex: 3 }} />
      <div style={{ position: 'absolute', bottom: 0, left: 0, width: 14, height: 14, borderBottom: '1px solid rgba(139,92,246,0.6)', borderLeft: '1px solid rgba(139,92,246,0.6)', pointerEvents: 'none', zIndex: 3 }} />
      <div style={{ position: 'absolute', bottom: 0, right: 0, width: 14, height: 14, borderBottom: '1px solid rgba(139,92,246,0.6)', borderRight: '1px solid rgba(139,92,246,0.6)', pointerEvents: 'none', zIndex: 3 }} />

      {/* Status bar */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 3,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '2px 8px', background: 'rgba(0,0,0,0.65)', pointerEvents: 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: faceCount > 0 ? 'rgba(167,139,250,1)' : 'rgba(100,116,139,0.5)' }} />
          <span style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.75)', letterSpacing: '0.2em', textTransform: 'uppercase' }}>
            {faceCount > 0 ? `${faceCount} FACE${faceCount > 1 ? 'S' : ''} · 468 PTS` : 'SCANNING'}
          </span>
        </div>
        <span style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.4)', letterSpacing: '0.15em' }}>MEDIAPIPE</span>
      </div>

      {/* Close */}
      <button onClick={disable} style={{
        position: 'absolute', top: 4, right: 4, zIndex: 4,
        width: 18, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(139,92,246,0.3)',
        cursor: 'pointer', color: 'rgba(167,139,250,0.7)', fontSize: 9, borderRadius: 2,
      }}>✕</button>
    </div>
  )
}
