/**
 * Shared camera stream singleton.
 * Only one getUserMedia call is ever made. Both the AI frame-capture hook
 * and the Luna camera display panel share the same MediaStream.
 */

let _stream: MediaStream | null = null
let _pending: Promise<MediaStream | null> | null = null
let _selectedDeviceId: string | null = (() => {
  try { return localStorage.getItem('luna_camera_device') } catch { return null }
})()

export function getSelectedCameraDeviceId(): string | null {
  return _selectedDeviceId
}

export function setCameraDevice(deviceId: string | null): void {
  _selectedDeviceId = deviceId
  try {
    if (deviceId) localStorage.setItem('luna_camera_device', deviceId)
    else localStorage.removeItem('luna_camera_device')
  } catch {}
  if (_stream) {
    _stream.getTracks().forEach(t => t.stop())
    _stream = null
  }
  _pending = null
}

export async function acquireCameraStream(): Promise<MediaStream | null> {
  if (_stream?.active) return _stream
  if (_pending) return _pending

  const videoConstraint: MediaTrackConstraints = _selectedDeviceId
    ? { deviceId: { exact: _selectedDeviceId }, width: 640, height: 480 }
    : { width: 640, height: 480, facingMode: 'user' }

  _pending = navigator.mediaDevices
    .getUserMedia({ video: videoConstraint, audio: false })
    .then(s => { _stream = s; return s })
    .catch(() => null)
    .finally(() => { _pending = null })

  return _pending
}

export function getCachedStream(): MediaStream | null {
  return _stream?.active ? _stream : null
}
