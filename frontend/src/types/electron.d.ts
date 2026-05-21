export {}

declare global {
  interface Window {
    electronAPI?: {
      minimize:           () => Promise<void>
      maximize:           () => Promise<void>
      toggleFullscreen:   () => Promise<void>
      isFullscreen:       () => Promise<boolean>
      close:              () => Promise<void>
      isMaximized:        () => Promise<boolean>
      onMaximizeChange:   (cb: (maximized: boolean) => void) => (() => void) | undefined
      onFullscreenChange: (cb: (fs: boolean) => void) => (() => void) | undefined
      notify:          (title: string, body: string) => Promise<void>
      openUrl:             (url: string) => Promise<void>
      quit?:               () => Promise<void>
      getLocation?:        () => Promise<{ lat: number | null; lon: number | null; accuracy: number | null }>
      spotifyOpenAuth?:    (authUrl: string) => Promise<null>
      onSpotifyConnected?: (cb: () => void) => (() => void)
      copyText?:           (text: string) => Promise<void>
      awayEnter?:          () => Promise<void>
      awayExit?:           () => Promise<void>
      apiBase:             string
      isElectron:          boolean
    }
  }
}
