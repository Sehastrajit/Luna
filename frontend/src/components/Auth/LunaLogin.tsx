import { useState } from 'react'
import { setLunaKey } from '../../api/client'

export function LunaLogin({ onAuth }: { onAuth: () => void }) {
  const [key, setKey] = useState('')
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(false)
    try {
      const res = await fetch('/api/auth/check', {
        headers: { 'X-Luna-Key': key },
      })
      const d = await res.json()
      if (d.valid) {
        setLunaKey(key)
        onAuth()
      } else {
        setError(true)
      }
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-luna-bg" style={{ gap: 24 }}>
      <div className="flex flex-col items-center" style={{ gap: 8 }}>
        <p
          className="text-xs tracking-widest uppercase"
          style={{ color: 'rgba(139,92,246,0.7)', letterSpacing: '0.2em' }}
        >
          luna
        </p>
        <p className="text-sm" style={{ color: 'rgba(100,116,139,0.6)' }}>
          enter your access key
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col items-center" style={{ gap: 12 }}>
        <input
          type="password"
          value={key}
          onChange={e => setKey(e.target.value)}
          placeholder="access key"
          autoFocus
          className="bg-transparent text-center text-sm focus:outline-none"
          style={{
            color: 'rgba(255,255,255,0.85)',
            borderBottom: `1px solid ${error ? 'rgba(239,68,68,0.6)' : 'rgba(139,92,246,0.4)'}`,
            paddingBottom: 6,
            width: 200,
            letterSpacing: '0.1em',
          }}
        />
        {error && (
          <p className="text-xs" style={{ color: 'rgba(239,68,68,0.7)' }}>
            wrong key
          </p>
        )}
        <button
          type="submit"
          disabled={loading || !key}
          className="text-xs tracking-widest uppercase transition-colors"
          style={{
            color: loading || !key ? 'rgba(100,116,139,0.3)' : 'rgba(139,92,246,0.8)',
            letterSpacing: '0.18em',
            marginTop: 4,
          }}
        >
          {loading ? 'checking...' : 'unlock'}
        </button>
      </form>
    </div>
  )
}
