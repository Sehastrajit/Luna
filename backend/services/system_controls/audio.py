"""Volume and mute controls."""
import shutil

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, _run, _osascript, _ps


def get_volume() -> tuple[bool, int | str]:
    if IS_MAC:
        rc, out = _osascript("output volume of (get volume settings)")
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, f"osascript error: {out}"

    if IS_WINDOWS:
        rc, out = _ps("$obj = New-Object -ComObject SAPI.SpVoice; $obj.Volume")
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, "Could not read system volume on Windows"

    if shutil.which("pactl"):
        rc, out = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        if rc == 0:
            import re
            m = re.search(r"(\d+)%", out)
            if m:
                return True, int(m.group(1))
    if shutil.which("amixer"):
        rc, out = _run(["amixer", "get", "Master"])
        if rc == 0:
            import re
            m = re.search(r"\[(\d+)%\]", out)
            if m:
                return True, int(m.group(1))
    return False, "Could not read volume — install pulseaudio-utils or alsa-utils"


def set_volume(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))

    if IS_MAC:
        rc, out = _osascript(f"set volume output volume {level}")
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)

    if IS_WINDOWS:
        if shutil.which("nircmd"):
            nircmd_val = int(level * 655.35)
            rc, out = _run(["nircmd", "setsysvolume", str(nircmd_val)])
            return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
        script = (
            f"$wsh = New-Object -ComObject wscript.shell;"
            f"1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }};"
            f"$steps = [math]::Round({level} / 2);"
            f"1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }}"
        )
        _ps(script)
        return True, f"Volume adjusted to approximately {level}%"

    if shutil.which("pactl"):
        rc, out = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    if shutil.which("amixer"):
        rc, out = _run(["amixer", "-q", "set", "Master", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    return False, "Could not set volume — install pulseaudio-utils or alsa-utils"


def mute_audio() -> tuple[bool, str]:
    if IS_MAC:
        rc, out = _osascript("set volume with output muted")
        return (rc == 0), ("Audio muted" if rc == 0 else out)

    if IS_WINDOWS:
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "1"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
        _ps("$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)")
        return True, "Audio muted"

    if IS_LINUX:
        if shutil.which("pactl"):
            rc, out = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
        if shutil.which("amixer"):
            rc, out = _run(["amixer", "-q", "set", "Master", "mute"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
    return False, "Could not mute audio on this platform"


def unmute_audio() -> tuple[bool, str]:
    if IS_MAC:
        rc, out = _osascript("set volume without output muted")
        return (rc == 0), ("Audio unmuted" if rc == 0 else out)

    if IS_WINDOWS:
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        _ps("$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)")
        return True, "Audio toggled"

    if IS_LINUX:
        if shutil.which("pactl"):
            rc, out = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        if shutil.which("amixer"):
            rc, out = _run(["amixer", "-q", "set", "Master", "unmute"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
    return False, "Could not unmute audio on this platform"
