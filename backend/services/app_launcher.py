"""
Windows app launcher — searches Start Menu, registry, and common paths.
"""
import os
import platform
import subprocess
import shutil
from difflib import get_close_matches
from pathlib import Path
from functools import lru_cache

try:
    import winreg
except ImportError:
    winreg = None


LUNA_APPS_DIR = Path("data/apps")
PLATFORM = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"
STICKY_NOTES_TARGET = "__sticky_notes__"


APP_PROFILES = {
    "chrome": {
        "aliases": ["chrome", "google chrome"],
        "windows": ["chrome"],
        "mac": ["app:Google Chrome"],
        "linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    },
    "firefox": {
        "aliases": ["firefox", "mozilla firefox"],
        "windows": ["firefox"],
        "mac": ["app:Firefox"],
        "linux": ["firefox"],
    },
    "edge": {
        "aliases": ["edge", "microsoft edge"],
        "windows": ["msedge"],
        "mac": ["app:Microsoft Edge"],
        "linux": ["microsoft-edge", "microsoft-edge-stable"],
    },
    "vscode": {
        "aliases": ["vscode", "vs code", "visual studio code", "code"],
        "windows": ["code"],
        "mac": ["app:Visual Studio Code", "code"],
        "linux": ["code", "codium"],
    },
    "spotify": {
        "aliases": ["spotify"],
        "windows": ["spotify"],
        "mac": ["app:Spotify"],
        "linux": ["spotify"],
    },
    "discord": {
        "aliases": ["discord"],
        "windows": ["discord"],
        "mac": ["app:Discord"],
        "linux": ["discord"],
    },
    "terminal": {
        "aliases": ["terminal", "windows terminal", "cmd", "command prompt", "powershell"],
        "windows": ["wt", "powershell", "cmd"],
        "mac": ["app:Terminal", "app:iTerm"],
        "linux": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "alacritty"],
    },
    "file_manager": {
        "aliases": ["explorer", "file explorer", "finder", "files", "file manager"],
        "windows": ["explorer"],
        "mac": ["app:Finder"],
        "linux": ["xdg-open:~", "nautilus", "dolphin", "thunar", "nemo"],
    },
    "calculator": {
        "aliases": ["calculator", "calc"],
        "windows": ["calc"],
        "mac": ["app:Calculator"],
        "linux": ["gnome-calculator", "kcalc", "qalculate-gtk", "galculator"],
    },
    "notes": {
        "aliases": ["sticky notes", "sticky note", "microsoft sticky notes", "windows sticky notes", "stickies", "notes"],
        "windows": [STICKY_NOTES_TARGET],
        "mac": ["app:Stickies", "app:Notes"],
        "linux": ["xpad", "indicator-stickynotes", "gnote", "tomboy"],
    },
    "notepad": {
        "aliases": ["notepad", "text editor", "editor"],
        "windows": ["notepad"],
        "mac": ["app:TextEdit"],
        "linux": ["gedit", "kate", "mousepad", "xed", "leafpad"],
    },
    "settings": {
        "aliases": ["settings", "system settings", "preferences"],
        "windows": ["ms-settings:"],
        "mac": ["app:System Settings", "app:System Preferences"],
        "linux": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
    },
    "paint": {
        "aliases": ["paint", "mspaint", "drawing"],
        "windows": ["mspaint"],
        "mac": ["app:Preview"],
        "linux": ["pinta", "kolourpaint", "drawing"],
    },
    "camera": {
        "aliases": ["camera", "webcam"],
        "windows": ["microsoft.windows.camera:"],
        "mac": ["app:Photo Booth"],
        "linux": ["cheese", "kamoso", "guvcview"],
    },
    "photos": {
        "aliases": ["photos", "pictures", "image viewer"],
        "windows": ["ms-photos:"],
        "mac": ["app:Photos", "app:Preview"],
        "linux": ["eog", "gwenview", "ristretto", "nomacs"],
    },
    "maps": {
        "aliases": ["maps", "map"],
        "windows": ["bingmaps:"],
        "mac": ["app:Maps"],
        "linux": ["xdg-open:https://maps.google.com"],
    },
    "office_word": {
        "aliases": ["word", "microsoft word"],
        "windows": ["winword"],
        "mac": ["app:Microsoft Word"],
        "linux": ["libreoffice --writer", "lowriter"],
    },
    "office_excel": {
        "aliases": ["excel", "microsoft excel"],
        "windows": ["excel"],
        "mac": ["app:Microsoft Excel"],
        "linux": ["libreoffice --calc", "localc"],
    },
    "office_powerpoint": {
        "aliases": ["powerpoint", "microsoft powerpoint"],
        "windows": ["powerpnt"],
        "mac": ["app:Microsoft PowerPoint"],
        "linux": ["libreoffice --impress", "loimpress"],
    },
    "outlook": {
        "aliases": ["outlook", "microsoft outlook", "mail"],
        "windows": ["outlook"],
        "mac": ["app:Microsoft Outlook", "app:Mail"],
        "linux": ["thunderbird", "evolution"],
    },
    "teams": {
        "aliases": ["teams", "microsoft teams"],
        "windows": ["teams", "ms-teams:"],
        "mac": ["app:Microsoft Teams"],
        "linux": ["teams-for-linux", "microsoft-teams"],
    },
    "store": {
        "aliases": ["store", "microsoft store", "app store"],
        "windows": ["ms-windows-store:"],
        "mac": ["app:App Store"],
        "linux": ["gnome-software", "plasma-discover"],
    },
    "task_manager": {
        "aliases": ["task manager", "activity monitor", "system monitor"],
        "windows": ["taskmgr"],
        "mac": ["app:Activity Monitor"],
        "linux": ["gnome-system-monitor", "ksysguard", "mate-system-monitor", "xfce4-taskmanager"],
    },
    "snipping": {
        "aliases": ["snipping tool", "screenshot tool", "screenshots"],
        "windows": ["SnippingTool", "ms-screenclip:"],
        "mac": ["app:Screenshot"],
        "linux": ["gnome-screenshot", "flameshot", "spectacle", "xfce4-screenshooter"],
    },
    "clock": {
        "aliases": ["clock", "alarms", "alarms and clock"],
        "windows": ["ms-clock:"],
        "mac": ["app:Clock"],
        "linux": ["gnome-clocks", "kclock"],
    },
}


def _get_luna_apps() -> dict[str, str]:
    """Scan Luna's own data/apps/ folder for .lnk shortcuts."""
    apps = {}
    if LUNA_APPS_DIR.exists():
        for lnk in LUNA_APPS_DIR.glob("*.lnk"):
            apps[lnk.stem.lower()] = str(lnk)
    return apps


COMMON_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "teams": "teams",
    "discord": "discord",
    "spotify": "spotify",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "terminal": "wt",
    "windows terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "paint": "mspaint",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "control panel": "control",
    "snipping tool": "SnippingTool",
    "clock": "ms-clock:",
    "photos": "ms-photos:",
    "camera": "microsoft.windows.camera:",
    "maps": "bingmaps:",
    "store": "ms-windows-store:",
    "sticky notes": STICKY_NOTES_TARGET,
    "sticky note": STICKY_NOTES_TARGET,
    "microsoft sticky notes": STICKY_NOTES_TARGET,
    "windows sticky notes": STICKY_NOTES_TARGET,
    "stickies": STICKY_NOTES_TARGET,
    "notes": STICKY_NOTES_TARGET,
}

STICKY_NOTES_APP_IDS = [
    "Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App",
]

STICKY_NOTES_PROTOCOLS = [
    "ms-sticky-notes:",
]


def _get_start_menu_apps() -> dict[str, str]:
    """Scan Start Menu for .lnk shortcuts."""
    apps = {}
    search_dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for lnk in search_dir.rglob("*.lnk"):
            name = lnk.stem.lower()
            apps[name] = str(lnk)
    return apps


@lru_cache(maxsize=1)
def _get_registry_apps() -> dict[str, str]:
    """Read installed apps from Windows Uninstall registry keys."""
    apps = {}
    if winreg is None:
        return apps
    keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
    ]
    for key_path in keys:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub_name = winreg.EnumKey(key, i)
                    sub_key = winreg.OpenKey(key, sub_name)
                    path, _ = winreg.QueryValueEx(sub_key, "")
                    apps[sub_name.lower().replace(".exe", "")] = path
                except Exception:
                    continue
        except Exception:
            continue
    return apps


@lru_cache(maxsize=1)
def _get_store_apps() -> dict[str, str]:
    """Read packaged apps from Get-StartApps."""
    apps = {}
    if not IS_WINDOWS:
        return apps
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-StartApps | ForEach-Object { \"$($_.Name)`t$($_.AppID)\" }",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return apps

    if result.returncode != 0:
        return apps

    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        name, app_id = line.split("\t", 1)
        name = name.strip().lower()
        app_id = app_id.strip()
        if name and app_id:
            apps[name] = f"shell:AppsFolder\\{app_id}"
    return apps


def _normalize(name: str) -> str:
    return " ".join(name.lower().replace(".exe", "").split())


def _platform_key() -> str:
    if IS_WINDOWS:
        return "windows"
    if IS_MAC:
        return "mac"
    return "linux"


def _profile_targets(query: str) -> list[str]:
    for profile in APP_PROFILES.values():
        aliases = {_normalize(alias) for alias in profile["aliases"]}
        if query in aliases or any(query in alias or alias in query for alias in aliases):
            return list(profile.get(_platform_key(), []))
    return []


def _first_available_target(targets: list[str]) -> str | None:
    if not targets:
        return None

    if IS_MAC:
        return targets[0]

    if IS_WINDOWS:
        for target in targets:
            if target == STICKY_NOTES_TARGET or target.endswith(":") or target.startswith("ms-") or target.startswith("shell:"):
                return target
            executable = target.split()[0]
            if shutil.which(executable):
                return target
        return targets[0]

    for target in targets:
        if target.startswith("xdg-open:"):
            return target
        executable = target.split()[0]
        if shutil.which(executable):
            return target
    return targets[0]


def _best_match(query: str, apps: dict[str, str]) -> str | None:
    if query in apps:
        return apps[query]

    for app_name, path in apps.items():
        if query in app_name or app_name in query:
            return path

    close = get_close_matches(query, apps.keys(), n=1, cutoff=0.72)
    if close:
        return apps[close[0]]
    return None


def _sticky_notes_candidates() -> list[str]:
    """
    Return known launch targets for Windows Sticky Notes.

    Sticky Notes has moved between classic Windows app, Microsoft Store UWP app,
    and newer Microsoft 365/OneNote-backed entrypoints. Prefer Start menu data
    from the current machine, then fall back to known package/protocol targets.
    """
    candidates: list[str] = []

    for apps in (_get_store_apps(), _get_start_menu_apps(), _get_luna_apps()):
        for app_name, target in apps.items():
            normalized = _normalize(app_name)
            if normalized in {"sticky notes", "microsoft sticky notes"}:
                candidates.insert(0, target)
            elif "sticky" in normalized and "note" in normalized:
                candidates.append(target)

    candidates.extend(f"shell:AppsFolder\\{app_id}" for app_id in STICKY_NOTES_APP_IDS)
    candidates.extend(STICKY_NOTES_PROTOCOLS)

    deduped = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _launch_target(target: str) -> None:
    """Launch a resolved Windows target."""
    if target.startswith("app:"):
        app_name = target.split(":", 1)[1]
        if IS_MAC:
            subprocess.Popen(["open", "-a", app_name])
            return
        raise OSError(f"app target is only supported on macOS: {app_name}")

    if target.startswith("xdg-open:"):
        uri = target.split(":", 1)[1]
        if uri == "~":
            uri = str(Path.home())
        if IS_LINUX:
            subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        raise OSError(f"xdg-open target is only supported on Linux: {uri}")

    if target.endswith(":") or target.startswith("ms-") or target.startswith("shell:"):
        os.startfile(target)
        return

    if target.endswith(".lnk"):
        os.startfile(target)
        return

    if Path(target).exists():
        os.startfile(target)
        return

    if IS_WINDOWS:
        subprocess.Popen([target], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return

    subprocess.Popen(target.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch_sticky_notes() -> tuple[bool, str]:
    """Open Microsoft Sticky Notes using the best available Windows entrypoint."""
    if not IS_WINDOWS:
        return False, "Sticky Notes is only available in the desktop Windows runtime."

    errors = []
    for target in _sticky_notes_candidates():
        try:
            _launch_target(target)
            return True, "Opened Sticky Notes"
        except Exception as e:
            errors.append(f"{target}: {e}")

    return (
        False,
        "Couldn't open Sticky Notes. Install Microsoft Sticky Notes from the Microsoft Store, "
        "or create a shortcut in data/apps/ named Sticky Notes.lnk.",
    )


def find_app(name: str) -> tuple[bool, str]:
    """
    Try to find an application by name.
    Returns (found, launch_target).
    """
    query = _normalize(name)

    profile_target = _first_available_target(_profile_targets(query))
    if profile_target:
        return True, profile_target

    if not IS_WINDOWS and shutil.which(query):
        return True, query

    if IS_MAC:
        return True, f"app:{name}"

    # Direct alias lookup
    if query in COMMON_APP_ALIASES:
        return True, COMMON_APP_ALIASES[query]

    # Partial alias match
    for alias, target in COMMON_APP_ALIASES.items():
        if query in alias or alias in query:
            return True, target

    for apps in (_get_luna_apps(), _get_registry_apps(), _get_start_menu_apps(), _get_store_apps()):
        target = _best_match(query, apps)
        if target:
            return True, target

    path_match = shutil.which(query)
    if path_match:
        return True, path_match

    if not IS_WINDOWS:
        return False, query

    # Final fallback: Windows can resolve some app aliases through ShellExecute.
    return True, query


def launch_app(name: str) -> tuple[bool, str]:
    """Launch an application. Returns (success, message)."""
    found, target = find_app(name)
    if not found:
        return False, f"Couldn't find an app matching '{name}' on this platform."

    if target == STICKY_NOTES_TARGET:
        return launch_sticky_notes()

    try:
        _launch_target(target)
        return True, f"Launched {name}"

    except Exception as e:
        return False, f"Couldn't launch {name}: {e}"


def list_known_apps() -> list[str]:
    """Return a combined list of findable app names."""
    names = []
    for profile in APP_PROFILES.values():
        if profile.get(_platform_key()):
            names += profile["aliases"]

    if not IS_WINDOWS:
        return sorted(set(names))

    names += list(COMMON_APP_ALIASES.keys())
    if _sticky_notes_candidates():
        names += ["sticky notes", "microsoft sticky notes", "sticky note"]
    names += list(_get_registry_apps().keys())
    names += list(_get_start_menu_apps().keys())
    names += list(_get_store_apps().keys())
    return sorted(set(names))


def list_app_profiles() -> dict:
    """Return curated app profile metadata for UI/docs/debug views."""
    platform_key = _platform_key()
    profiles = []
    for app_id, profile in APP_PROFILES.items():
        profiles.append({
            "id": app_id,
            "aliases": profile["aliases"],
            "platform": platform_key,
            "targets": profile.get(platform_key, []),
            "supported": bool(profile.get(platform_key)),
        })
    return {
        "platform": PLATFORM,
        "profiles": profiles,
    }
