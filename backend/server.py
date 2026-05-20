"""
Standalone entry point for the Luna FastAPI backend.
Called by Electron's main process — do not run directly unless testing.
"""
import sys
import os
import atexit
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is on the path when run as a subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Write PID file so Electron can cleanly kill this process on next launch
_PID_FILE = Path(__file__).parent.parent / "data" / "backend.pid"
_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
_PID_FILE.write_text(str(os.getpid()))

@atexit.register
def _cleanup_pid():
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

import uvicorn
from backend.config import settings

if __name__ == '__main__':
    uvicorn.run(
        'backend.main:app',
        host=settings.host,
        port=settings.port,
        log_level='warning',
    )
