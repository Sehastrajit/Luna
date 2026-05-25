import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../../store'
import { acquireCameraStream } from '../../../services/cameraStream'
import { P } from '../palette'

export function CameraFeed() {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef     = useRef<HTMLVideoElement>(null)
  const canvasRef    = useRef<HTMLCanvasElement>(null)
  const meshRef      = useRef<any>(null)
  const [state, setState] = useState<'loading' | 'active' | 'error'>('loading')
  const faceTracking = useStore(s => s.faceTrackingEnabled)

  useEffect(() => {
    const FaceMesh = (window as any).FaceMesh
    if (!FaceMesh) return
    const fm = new FaceMesh({ locateFile: (f: string) => `/mediapipe/${f}` })
    fm.setOptions({ maxNumFaces: 1, refineLandmarks: false, selfieMode: false,
      minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 })

    fm.onResults((results: any) => {
      const canvas = canvasRef.current
      const video  = videoRef.current
      if (!canvas || !video) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      // Canvas buffer = container's CSS pixel size
      const W = canvas.width
      const H = canvas.height
      ctx.clearRect(0, 0, W, H)

      const faces: any[][] = results.multiFaceLandmarks ?? []
      if (!faces.length) return

      // Match objectFit:cover — compute scale + crop offset so landmarks
      // land on the same pixels as the displayed video frame.
      const vw = video.videoWidth  || 640
      const vh = video.videoHeight || 480
      const containerAspect = W / H
      const videoAspect     = vw / vh
      let scale: number, offsetX: number, offsetY: number
      if (containerAspect > videoAspect) {
        scale   = W / vw
        offsetX = 0
        offsetY = (H - vh * scale) / 2
      } else {
        scale   = H / vh
        offsetX = (W - vw * scale) / 2
        offsetY = 0
      }

      const lx = (lms: any[], i: number) => lms[i].x * vw * scale + offsetX
      const ly = (lms: any[], i: number) => lms[i].y * vh * scale + offsetY
      const w = window as any

      for (const lms of faces) {
        ctx.strokeStyle = 'rgba(109,40,217,0.22)'; ctx.lineWidth = 0.55
        for (const [a, b] of (w.FACEMESH_TESSELATION ?? [])) {
          ctx.beginPath(); ctx.moveTo(lx(lms, a), ly(lms, a)); ctx.lineTo(lx(lms, b), ly(lms, b)); ctx.stroke()
        }
        ctx.strokeStyle = 'rgba(139,92,246,0.7)'; ctx.lineWidth = 1.2
        for (const [a, b] of (w.FACEMESH_FACE_OVAL ?? [])) {
          ctx.beginPath(); ctx.moveTo(lx(lms, a), ly(lms, a)); ctx.lineTo(lx(lms, b), ly(lms, b)); ctx.stroke()
        }
      }
    })

    meshRef.current = fm
    fm.initialize().catch(() => {})
    return () => { fm.close() }
  }, [])

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

  useEffect(() => {
    if (state !== 'active' || !faceTracking) {
      const canvas = canvasRef.current
      if (canvas) canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height)
      return
    }
    let stopped = false
    const tick = async () => {
      if (stopped) return
      const video = videoRef.current, fm = meshRef.current, canvas = canvasRef.current
      if (video && fm && canvas && video.readyState >= 2) {
        // Sync canvas buffer to the container's actual CSS size each frame
        const W = canvas.clientWidth
        const H = canvas.clientHeight
        if (W > 0 && H > 0 && (canvas.width !== W || canvas.height !== H)) {
          canvas.width  = W
          canvas.height = H
        }
        try { await fm.send({ image: video }) } catch { /* ignore */ }
      }
      if (!stopped) setTimeout(tick, 125)
    }
    tick()
    return () => { stopped = true }
  }, [state, faceTracking])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%', background: '#000', overflow: 'hidden' }}>
      {state !== 'active' && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textDim, fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.15em' }}>
          {state === 'loading' ? 'CONNECTING...' : 'NO SIGNAL'}
        </div>
      )}
      <video ref={videoRef} autoPlay muted playsInline
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: state === 'active' ? 'block' : 'none' }} />
      <canvas ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', display: state === 'active' ? 'block' : 'none' }} />
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.04) 3px, rgba(0,0,0,0.04) 4px)', mixBlendMode: 'overlay' }} />
    </div>
  )
}
