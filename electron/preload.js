'use strict'

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize:          ()  => ipcRenderer.invoke('window:minimize'),
  maximize:          ()  => ipcRenderer.invoke('window:maximize'),
  toggleFullscreen:  ()  => ipcRenderer.invoke('window:fullscreen'),
  isFullscreen:      ()  => ipcRenderer.invoke('window:is-fullscreen'),
  close:             ()  => ipcRenderer.invoke('window:close'),
  isMaximized:       ()  => ipcRenderer.invoke('window:is-maximized'),
  onMaximizeChange: cb  => {
    const handler = (_, val) => cb(val)
    ipcRenderer.on('window:maximized', handler)
    return () => ipcRenderer.removeListener('window:maximized', handler)
  },
  onFullscreenChange: cb => {
    const handler = (_, val) => cb(val)
    ipcRenderer.on('window:fullscreen-changed', handler)
    return () => ipcRenderer.removeListener('window:fullscreen-changed', handler)
  },

  // Native notifications (replaces pywin32)
  notify:  (title, body) => ipcRenderer.invoke('notify', { title, body }),

  // Open links in system browser
  openUrl: url => ipcRenderer.invoke('open-url', url),

  // Spotify OAuth popup + connected event
  spotifyOpenAuth:    authUrl => ipcRenderer.invoke('spotify:open-auth', authUrl),
  onSpotifyConnected: cb => {
    const handler = () => cb()
    ipcRenderer.on('spotify:connected', handler)
    return () => ipcRenderer.removeListener('spotify:connected', handler)
  },

  // Quit the app
  quit: () => ipcRenderer.invoke('app:quit'),

  // Clipboard (navigator.clipboard fails silently in Electron without focus)
  copyText: text => ipcRenderer.invoke('clipboard:write', text),
  openSettings: () => ipcRenderer.invoke('settings:open'),
  checkForUpdates: () => ipcRenderer.invoke('update:check'),
  installUpdate: () => ipcRenderer.invoke('update:install'),
  onUpdateStatus: cb => {
    const handler = (_, status) => cb(status)
    ipcRenderer.on('update:status', handler)
    return () => ipcRenderer.removeListener('update:status', handler)
  },

  // Away mode — fullscreen on all displays
  awayEnter: () => ipcRenderer.invoke('away:enter'),
  awayExit:  () => ipcRenderer.invoke('away:exit'),

  // IP-based geolocation (works without OS/browser permissions)
  getLocation: () => ipcRenderer.invoke('location:get'),

  // API base URL — Electron loads index.html directly, so relative paths won't work
  apiBase:    'http://127.0.0.1:8899',
  isElectron: true,
})
