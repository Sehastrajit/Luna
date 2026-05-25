import { useEffect, useState } from 'react'
import { P } from '../palette'
import { fetchLuna } from '../lunaDashboardApi'

// Backend returns raw (moondream combined text) and history (LLM session summary)
interface VisionCtx {
  active: boolean
  raw?: string
  history?: string
  captured_at?: number
}

export function AwarenessWidget() {
  const [ctx, setCtx] = useState<VisionCtx | null>(null)
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

  if (status === 'loading') return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: P.textDim, fontFamily: 'monospace', fontSize: 10 }}>
      WAITING...
    </div>
  )

  if (!ctx?.active || !ctx.raw) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 5 }}>
      <span style={{ fontFamily: 'monospace', fontSize: 10, color: P.textDim }}>NO SIGNAL</span>
      <span style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.5)', textAlign: 'center', maxWidth: 140, lineHeight: 1.5 }}>
        moondream analyses every 30s
      </span>
    </div>
  )

  const age = ctx.captured_at ? Math.round((Date.now() / 1000) - ctx.captured_at) : null

  return (
    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6, height: '100%', justifyContent: 'center', overflowY: 'auto', scrollbarWidth: 'none' }}>
      <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.accent, letterSpacing: '0.2em' }}>NOW</div>
      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.78)', lineHeight: 1.5 }}>{ctx.raw}</div>

      {ctx.history && (
        <>
          <div style={{ fontFamily: 'monospace', fontSize: 8, color: P.textDim, letterSpacing: '0.2em', marginTop: 4 }}>SESSION</div>
          <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.48)', lineHeight: 1.45 }}>{ctx.history}</div>
        </>
      )}

      {age !== null && (
        <div style={{ fontFamily: 'monospace', fontSize: 8, color: 'rgba(100,116,139,0.45)', marginTop: 2 }}>
          updated {age < 60 ? `${age}s` : `${Math.round(age / 60)}m`} ago
        </div>
      )}
    </div>
  )
}
