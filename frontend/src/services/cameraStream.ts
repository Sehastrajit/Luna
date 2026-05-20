/**
 * Shared camera stream singleton.
 * Only one getUserMedia call is ever made. Both the AI frame-capture hook
 * and the Luna camera display panel share the same MediaStream.
 */

let _stream: MediaStream | null = null
let _pending: Promise<MediaStream | null> | null = null

export async function acquireCameraStream(): Promise<MediaStream | null> {
  if (_stream?.active) return _stream
  if (_pending) return _pending

  _pending = navigator.mediaDevices
    .getUserMedia({
      video: { width: 640, height: 480, facingMode: 'user' },
      audio: false,
    })
    .then(s => {
      _stream = s
      return s
    })
    .catch(() => null)
    .finally(() => { _pending = null })

  return _pending
}

export function getCachedStream(): MediaStream | null {
  return _stream?.active ? _stream : null
}
