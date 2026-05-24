import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { VoiceOrb } from '../Voice/VoiceOrb'
import { SpeakerPicker } from './SpeakerPicker'
import { LunaDashboardToggle } from '../Luna/LunaDashboardToggle'
import { Minus, Square, X, Maximize2, Minimize2, Settings } from 'lucide-react'

function TrafficLights({ maximized, fullscreen }: { maximized: boolean; fullscreen: boolean }) {
  const stopDrag = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
  }

  return (
    <div className="flex items-center h-full" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.minimize()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title="Minimize"
      >
        <Minus size={14} strokeWidth={2} />
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.maximize()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title={maximized ? 'Restore' : 'Maximize'}
      >
        <Square size={12} strokeWidth={2} />
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.toggleFullscreen()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
        title={fullscreen ? 'Exit fullscreen (F11)' : 'Fullscreen (F11)'}
      >
        {fullscreen ? <Minimize2 size={13} strokeWidth={2} /> : <Maximize2 size={13} strokeWidth={2} />}
      </button>
      <button
        onMouseDown={stopDrag}
        onClick={() => window.electronAPI?.close()}
        className="h-full w-11 flex items-center justify-center text-luna-dim hover:bg-red-500/80 hover:text-white transition-colors"
        title="Close to tray"
      >
        <X size={15} strokeWidth={2} />
      </button>
    </div>
  )
}

export function TitleBar() {
  const [maximized, setMaximized]   = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const { viewMode, toggleViewMode, openSettings } = useStore()

  useEffect(() => {
    window.electronAPI?.isMaximized().then(setMaximized)
    window.electronAPI?.isFullscreen?.().then(setFullscreen)
    const cleanMax  = window.electronAPI?.onMaximizeChange(setMaximized)
    const cleanFull = window.electronAPI?.onFullscreenChange?.(setFullscreen)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'F11') { e.preventDefault(); window.electronAPI?.toggleFullscreen() } }
    window.addEventListener('keydown', onKey)
    return () => { cleanMax?.(); cleanFull?.(); window.removeEventListener('keydown', onKey) }
  }, [])

  // ── User mode: bare strip — orb on left, traffic lights on right ──────────
  if (viewMode === 'user') {
    return (
      <div
        className="relative z-40 h-10 flex items-center justify-between bg-luna-surface border-b border-luna-border shrink-0 select-none"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div
          className="flex items-center gap-3 px-4 h-full"
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <VoiceOrb size={28} onToggle={toggleViewMode} />
          <span className="text-[10px] font-mono tracking-[0.3em] text-luna-dim uppercase">
            Luna
          </span>
        </div>
        <div className="flex items-center h-full" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        <LunaDashboardToggle />
        <div className="w-px h-4 bg-luna-border mx-1" />
        <SpeakerPicker />
        <div className="w-px h-4 bg-luna-border mx-1" />
        <button
          onMouseDown={(event) => event.stopPropagation()}
          onClick={() => openSettings()}
          className="h-full w-10 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
          title="Settings"
        >
          <Settings size={14} strokeWidth={2} />
        </button>
        <div className="w-px h-4 bg-luna-border mx-1" />
        <TrafficLights maximized={maximized} fullscreen={fullscreen} />
        </div>
      </div>
    )
  }

  // ── Dev mode: full title bar ──────────────────────────────────────────────
  return (
    <div
      className="relative z-40 h-10 flex items-center justify-between bg-luna-surface border-b border-luna-border shrink-0 select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      <span className="px-4 text-[10px] font-mono tracking-[0.3em] text-luna-dim uppercase">
        Luna
      </span>
      <div
        className="flex items-center gap-3 h-full"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        <VoiceOrb size={36} onToggle={toggleViewMode} />
        <div className="w-px h-4 bg-luna-border" />
        <LunaDashboardToggle />
        <div className="w-px h-4 bg-luna-border" />
        <SpeakerPicker />
        <div className="w-px h-4 bg-luna-border" />
        <button
          onMouseDown={(event) => event.stopPropagation()}
          onClick={() => openSettings()}
          className="h-full w-10 flex items-center justify-center text-luna-dim hover:bg-white/10 hover:text-luna-text transition-colors"
          title="Settings"
        >
          <Settings size={14} strokeWidth={2} />
        </button>
        <div className="w-px h-4 bg-luna-border" />
        <TrafficLights maximized={maximized} fullscreen={fullscreen} />
      </div>
    </div>
  )
}
