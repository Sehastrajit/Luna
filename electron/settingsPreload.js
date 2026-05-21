'use strict'

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('lunaSetup', {
  get: () => ipcRenderer.invoke('setup:get'),
  save: config => ipcRenderer.invoke('setup:save', config),
})
