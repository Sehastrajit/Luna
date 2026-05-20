import { useEffect, useRef } from 'react'
import { acquireCameraStream } from '../services/cameraStream'

const CAPTURE_INTERVAL_MS = 30_000
const JPEG_QUALITY = 0.5

function getLunaKey(): string {
  return localStorage.getItem('luna_key') || (window as any).electronAPI?.lunaKey || ''
}
function getBase(): string {
  return (window as any).electronAPI?.apiBase ?? ''
}

async function sendFrame(b64: string): Promise<void> {
  const key = getLunaKey()
  await fetch(`${getBase()}/api/vision/frame`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { 'X-Luna-Key': key } : {}),
    },
    body: JSON.stringify({ image: b64 }),
  })
}

export function useCamera(): void {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

    async function start() {
      const stream = await acquireCameraStream()
      if (!stream || cancelled) return

      const video = document.createElement('video')
      video.srcObject = stream
      video.muted = true
      video.playsInline = true
      await video.play().catch(() => {})
      if (cancelled) return
      videoRef.current = video

      const capture = () => {
        const vid = videoRef.current
        if (!vid || vid.readyState < 2) return
        const canvas = document.createElement('canvas')
        canvas.width = vid.videoWidth || 640
        canvas.height = vid.videoHeight || 480
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        ctx.drawImage(vid, 0, 0)
        const b64 = canvas.toDataURL('image/jpeg', JPEG_QUALITY).split(',')[1]
        if (b64) sendFrame(b64).catch(() => {})
      }

      setTimeout(capture, 2500)
      timerRef.current = setInterval(capture, CAPTURE_INTERVAL_MS)
    }

    start()

    return () => {
      cancelled = true
      if (timerRef.current) clearInterval(timerRef.current)
      // Do NOT stop the stream — it is shared via cameraStream singleton
      videoRef.current = null
    }
  }, [])
}
