"""
Cross-platform system controls — volume, brightness, lock screen, sleep.

All functions return (success: bool, message: str).
No external dependencies required — uses OS-native commands only.

  Windows : PowerShell / rundll32 / WMI
  macOS   : osascript / pmset / brightness CLI
  Linux   : pactl / amixer / xrandr / brightnessctl / loginctl / systemctl
"""
import platform
import subprocess
import shutil

PLATFORM   = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC     = PLATFORM == "Darwin"
IS_LINUX   = PLATFORM == "Linux"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    """Run a command and return (returncode, combined output)."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}),
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return -1, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def _osascript(script: str) -> tuple[int, str]:
    return _run(["osascript", "-e", script])


def _ps(command: str) -> tuple[int, str]:
    return _run(["powershell", "-NoProfile", "-Command", command])


# ── Volume ────────────────────────────────────────────────────────────────────

def get_volume() -> tuple[bool, int | str]:
    """
    Return (success, level) where level is 0-100.
    On failure returns (False, error_message).
    """
    if IS_MAC:
        rc, out = _osascript("output volume of (get volume settings)")
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, f"osascript error: {out}"

    if IS_WINDOWS:
        script = (
            "Add-Type -TypeDefinition '"
            "using System.Runtime.InteropServices;"
            "[Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"),"
            "InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]"
            "public interface IAudioEndpointVolume {"
            "  int f(); int f2(); int f3();"
            "  int SetMasterVolumeLevelScalar(float f, System.Guid g);"
            "  int f5(); int f6(); int f7(); int f8();"
            "  int GetMasterVolumeLevelScalar(out float f);"
            "}' -PassThru | Out-Null; "
            # Simpler: use WScript.Shell SendKeys approach or SoundMixer
            # Fall back to a registry read which isn't reliable, so use nircmd check
            "$vol = [math]::Round((Get-WmiObject -Class Win32_SoundDevice | "
            "Select-Object -First 1).StatusInfo); $vol"
        )
        # Simpler reliable approach: use SoundVolumeView / nircmd if present
        if shutil.which("nircmd"):
            # nircmd doesn't easily report volume; use PowerShell Audio policy
            pass
        # Reliable fallback: read via PowerShell COM
        rc, out = _ps(
            "[math]::Round((New-Object -ComObject WScript.Shell)."
            "Exec('powershell -command \"(Get-AudioDevice -Playback).Volume\"').StdOut.ReadAll())"
        )
        # Most reliable Windows approach without extra modules:
        rc, out = _ps(
            "$vol = [System.Math]::Round([System.Runtime.InteropServices.Marshal]::GetActiveObject('WMPlayer.OCX.7') | "
            "Select-Object -ExpandProperty settings | Select-Object -ExpandProperty volume);"
            "if ($vol) { $vol } else { "
            "Add-Type -AssemblyName System.Windows.Forms;"
            "[System.Windows.Forms.SendKeys]::SendWait(''); 50 }"  # placeholder
        )
        # Use the most universally available method
        rc, out = _ps(
            "$obj = New-Object -ComObject SAPI.SpVoice; $obj.Volume"
        )
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, "Could not read system volume on Windows"

    # Linux
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
    """
    Set system volume to level (0–100).
    """
    level = max(0, min(100, int(level)))

    if IS_MAC:
        rc, out = _osascript(f"set volume output volume {level}")
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)

    if IS_WINDOWS:
        # Use nircmd if installed (most reliable)
        if shutil.which("nircmd"):
            nircmd_val = int(level * 655.35)
            rc, out = _run(["nircmd", "setsysvolume", str(nircmd_val)])
            return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
        # PowerShell via WScript COM
        script = (
            f"$wsh = New-Object -ComObject wscript.shell;"
            f"1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }};"  # volume down to 0
            f"$steps = [math]::Round({level} / 2);"
            f"1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }}"  # volume up
        )
        rc, out = _ps(script)
        return True, f"Volume adjusted to approximately {level}%"

    # Linux
    if shutil.which("pactl"):
        rc, out = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    if shutil.which("amixer"):
        rc, out = _run(["amixer", "-q", "set", "Master", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    return False, "Could not set volume — install pulseaudio-utils or alsa-utils"


def mute_audio() -> tuple[bool, str]:
    """Mute system audio output."""
    if IS_MAC:
        rc, out = _osascript("set volume with output muted")
        return (rc == 0), ("Audio muted" if rc == 0 else out)

    if IS_WINDOWS:
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "1"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
        rc, out = _ps(
            "$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)"
        )
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
    """Unmute system audio output."""
    if IS_MAC:
        rc, out = _osascript("set volume without output muted")
        return (rc == 0), ("Audio unmuted" if rc == 0 else out)

    if IS_WINDOWS:
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        rc, out = _ps(
            "$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)"
        )
        return True, "Audio toggled"

    if IS_LINUX:
        if shutil.which("pactl"):
            rc, out = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        if shutil.which("amixer"):
            rc, out = _run(["amixer", "-q", "set", "Master", "unmute"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
    return False, "Could not unmute audio on this platform"


# ── Brightness ────────────────────────────────────────────────────────────────

def get_brightness() -> tuple[bool, int | str]:
    """Return (success, level 0-100) or (False, error)."""
    if IS_MAC:
        if shutil.which("brightness"):
            rc, out = _run(["brightness", "-l"])
            if rc == 0:
                import re
                m = re.search(r"brightness\s+([0-9.]+)", out)
                if m:
                    return True, int(float(m.group(1)) * 100)
        rc, out = _osascript(
            "tell application \"System Events\" to key code 0"
        )
        return False, "Install 'brightness' CLI: brew install brightness"

    if IS_WINDOWS:
        rc, out = _ps(
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
        )
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, "Could not read brightness (laptop display required)"

    if IS_LINUX:
        for tool in ["brightnessctl", "xbacklight", "light"]:
            if not shutil.which(tool):
                continue
            if tool == "brightnessctl":
                rc, out = _run(["brightnessctl", "get"])
                if rc == 0:
                    rc2, out2 = _run(["brightnessctl", "max"])
                    if rc2 == 0 and out.strip().isdigit() and out2.strip().isdigit():
                        pct = int(int(out.strip()) / int(out2.strip()) * 100)
                        return True, pct
            elif tool == "xbacklight":
                rc, out = _run(["xbacklight", "-get"])
                if rc == 0:
                    return True, int(float(out.strip()))
            elif tool == "light":
                rc, out = _run(["light", "-G"])
                if rc == 0:
                    return True, int(float(out.strip()))
    return False, "Could not read brightness — install brightnessctl or xbacklight"


def set_brightness(level: int) -> tuple[bool, str]:
    """Set display brightness to level (0–100)."""
    level = max(0, min(100, int(level)))

    if IS_MAC:
        if shutil.which("brightness"):
            rc, out = _run(["brightness", str(level / 100)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        return False, "Install 'brightness' CLI: brew install brightness"

    if IS_WINDOWS:
        rc, out = _ps(
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
            f".WmiSetBrightness(1, {level})"
        )
        return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else
                           f"Could not set brightness — {out}")

    if IS_LINUX:
        if shutil.which("brightnessctl"):
            rc, out = _run(["brightnessctl", "set", f"{level}%"])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        if shutil.which("xbacklight"):
            rc, out = _run(["xbacklight", "-set", str(level)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        if shutil.which("light"):
            rc, out = _run(["light", "-S", str(level)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
    return False, "Could not set brightness — install brightnessctl or xbacklight"


# ── Lock screen ───────────────────────────────────────────────────────────────

def lock_screen() -> tuple[bool, str]:
    """Lock the workstation / screen."""
    if IS_WINDOWS:
        rc, out = _run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return (rc == 0), ("Screen locked" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript(
            'tell application "System Events" to keystroke "q" '
            'using {command down, control down}'
        )
        if rc != 0:
            rc, out = _run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                 "-suspend"]
            )
        return (rc == 0), ("Screen locked" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "--lock"],
            ["xscreensaver-command", "-lock"],
            ["qdbus", "org.kde.screensaver", "/ScreenSaver", "Lock"],
            ["slock"],
            ["i3lock"],
        ]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "Screen locked"
        return False, "Could not lock screen — install loginctl or xdg-screensaver"

    return False, f"Lock screen not supported on {PLATFORM}"


# ── Sleep ─────────────────────────────────────────────────────────────────────

def sleep_system() -> tuple[bool, str]:
    """Put the system to sleep / suspend."""
    if IS_WINDOWS:
        rc, out = _ps("Add-Type -Assembly System.Windows.Forms; "
                      "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)")
        if rc != 0:
            rc, out = _run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"]
            )
        return (rc == 0), ("System going to sleep" if rc == 0 else out)

    if IS_MAC:
        rc, out = _run(["pmset", "sleepnow"])
        return (rc == 0), ("System going to sleep" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [
            ["systemctl", "suspend"],
            ["pm-suspend"],
            ["loginctl", "suspend"],
        ]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "System going to sleep"
        return False, "Could not suspend — install systemd or pm-utils"

    return False, f"Sleep not supported on {PLATFORM}"


# ── Shutdown / restart (dangerous) ────────────────────────────────────────────

def shutdown_system(delay_seconds: int = 0) -> tuple[bool, str]:
    """Initiate system shutdown. Requires explicit user confirmation."""
    if IS_WINDOWS:
        rc, out = _run(["shutdown", "/s", "/t", str(delay_seconds)])
        return (rc == 0), (f"Shutting down in {delay_seconds}s" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript(f'tell app "System Events" to shut down')
        return (rc == 0), ("Shutting down" if rc == 0 else out)

    if IS_LINUX:
        rc, out = _run(["systemctl", "poweroff"])
        return (rc == 0), ("Shutting down" if rc == 0 else out)

    return False, f"Shutdown not supported on {PLATFORM}"


def restart_system(delay_seconds: int = 0) -> tuple[bool, str]:
    """Restart the system. Requires explicit user confirmation."""
    if IS_WINDOWS:
        rc, out = _run(["shutdown", "/r", "/t", str(delay_seconds)])
        return (rc == 0), (f"Restarting in {delay_seconds}s" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript('tell app "System Events" to restart')
        return (rc == 0), ("Restarting" if rc == 0 else out)

    if IS_LINUX:
        rc, out = _run(["systemctl", "reboot"])
        return (rc == 0), ("Restarting" if rc == 0 else out)

    return False, f"Restart not supported on {PLATFORM}"


# ── Display ───────────────────────────────────────────────────────────────────

def turn_off_display() -> tuple[bool, str]:
    """Turn off the display (does not sleep the system)."""
    if IS_WINDOWS:
        import ctypes
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        return True, "Display turned off"

    if IS_MAC:
        rc, out = _run(["pmset", "displaysleepnow"])
        return (rc == 0), ("Display turned off" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [["xset", "dpms", "force", "off"], ["xrandr", "--display", ":0", "--off"]]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "Display turned off"
    return False, "Could not turn off display"


# ── Clipboard ─────────────────────────────────────────────────────────────────

def get_clipboard() -> tuple[bool, str]:
    """Read current clipboard text content."""
    if IS_WINDOWS:
        rc, out = _ps("Get-Clipboard")
        return (rc == 0), out

    if IS_MAC:
        rc, out = _run(["pbpaste"])
        return (rc == 0), out

    if IS_LINUX:
        for tool, args in [
            ("xclip", ["-selection", "clipboard", "-o"]),
            ("xsel",  ["--clipboard", "--output"]),
            ("wl-paste", []),
        ]:
            if shutil.which(tool):
                rc, out = _run([tool] + args)
                if rc == 0:
                    return True, out
    return False, "Could not read clipboard"


def set_clipboard(text: str) -> tuple[bool, str]:
    """Write text to the system clipboard."""
    if IS_WINDOWS:
        rc, out = _ps(f"Set-Clipboard -Value '{text.replace(chr(39), chr(34))}'")
        return (rc == 0), ("Copied to clipboard" if rc == 0 else out)

    if IS_MAC:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(text.encode())
        return True, "Copied to clipboard"

    if IS_LINUX:
        for tool, args in [
            ("xclip", ["-selection", "clipboard"]),
            ("xsel",  ["--clipboard", "--input"]),
            ("wl-copy", []),
        ]:
            if shutil.which(tool):
                proc = subprocess.Popen([tool] + args, stdin=subprocess.PIPE)
                proc.communicate(text.encode())
                return True, "Copied to clipboard"
    return False, "Could not write to clipboard — install xclip or xsel"


# ── System info ───────────────────────────────────────────────────────────────

def get_system_info() -> dict:
    """Return basic OS/hardware info."""
    import platform as _p
    info: dict = {
        "os":      PLATFORM,
        "version": _p.version(),
        "machine": _p.machine(),
        "node":    _p.node(),
    }

    if IS_WINDOWS:
        rc, out = _ps("(Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB")
        if rc == 0:
            try:
                info["ram_gb"] = round(float(out.strip()), 1)
            except ValueError:
                pass
        rc, out = _ps("(Get-WmiObject Win32_Battery).EstimatedChargeRemaining")
        if rc == 0 and out.strip().isdigit():
            info["battery_pct"] = int(out.strip())

    if IS_MAC:
        rc, out = _run(["sysctl", "-n", "hw.memsize"])
        if rc == 0 and out.strip().isdigit():
            info["ram_gb"] = round(int(out.strip()) / 1_073_741_824, 1)
        rc, out = _run(["pmset", "-g", "batt"])
        if rc == 0:
            import re
            m = re.search(r"(\d+)%", out)
            if m:
                info["battery_pct"] = int(m.group(1))

    if IS_LINUX:
        try:
            mem = Path("/proc/meminfo").read_text()
            import re
            m = re.search(r"MemTotal:\s+(\d+)", mem)
            if m:
                info["ram_gb"] = round(int(m.group(1)) / 1_048_576, 1)
        except Exception:
            pass
        batt = Path("/sys/class/power_supply/BAT0/capacity")
        if batt.exists():
            info["battery_pct"] = int(batt.read_text().strip())

    return info
