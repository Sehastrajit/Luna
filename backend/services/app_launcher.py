"""
Windows app launcher — searches Start Menu, registry, and common paths.
"""
import os
import subprocess
import winreg
import shutil
from difflib import get_close_matches
from pathlib import Path
from functools import lru_cache


LUNA_APPS_DIR = Path("data/apps")


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
}


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


def find_app(name: str) -> tuple[bool, str]:
    """
    Try to find an application by name.
    Returns (found, launch_target).
    """
    query = _normalize(name)

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

    # Final fallback: Windows can resolve some app aliases through ShellExecute.
    return True, query


def launch_app(name: str) -> tuple[bool, str]:
    """Launch an application. Returns (success, message)."""
    found, target = find_app(name)

    try:
        # Shell / ms-protocol URLs (Settings, Store, packaged apps, etc.)
        if target.endswith(":") or target.startswith("ms-") or target.startswith("shell:"):
            os.startfile(target)
            return True, f"Opened {name}"

        # .lnk shortcuts
        if target.endswith(".lnk"):
            os.startfile(target)
            return True, f"Launched {name}"

        if Path(target).exists():
            os.startfile(target)
            return True, f"Launched {name}"

        # PATH executable or app execution alias.
        subprocess.Popen([target], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return True, f"Launched {name}"

    except Exception as e:
        return False, f"Couldn't launch {name}: {e}"


def list_known_apps() -> list[str]:
    """Return a combined list of findable app names."""
    names = list(COMMON_APP_ALIASES.keys())
    names += list(_get_registry_apps().keys())
    names += list(_get_start_menu_apps().keys())
    names += list(_get_store_apps().keys())
    return sorted(set(names))
