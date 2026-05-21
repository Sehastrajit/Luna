"""
Cross-platform app launcher — Windows, macOS, Linux.

Discovery order:
  1. APP_PROFILES  — curated cross-platform app catalogue (aliases → per-OS targets)
  2. macOS Spotlight  — mdfind search for any .app bundle
  3. Linux .desktop   — XDG application entries in standard directories
  4. Windows registry — App Paths + packaged Store apps + Start Menu .lnk shortcuts
  5. PATH fallback    — shutil.which()
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
IS_MAC     = PLATFORM == "Darwin"
IS_LINUX   = PLATFORM == "Linux"
STICKY_NOTES_TARGET = "__sticky_notes__"


# ── App profiles ──────────────────────────────────────────────────────────────
# Each profile has:
#   aliases  — names / phrases Luna recognises
#   windows  — executable names / URI schemes / .exe paths
#   mac      — "app:Name" for open -a, or a plain command
#   linux    — binary names tried in order; "xdg-open:URI" for URL fallbacks

APP_PROFILES = {

    # ── Browsers ──────────────────────────────────────────────────────────────
    "chrome": {
        "aliases": ["chrome", "google chrome"],
        "windows": ["chrome"],
        "mac":     ["app:Google Chrome"],
        "linux":   ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    },
    "firefox": {
        "aliases": ["firefox", "mozilla firefox"],
        "windows": ["firefox"],
        "mac":     ["app:Firefox"],
        "linux":   ["firefox"],
    },
    "edge": {
        "aliases": ["edge", "microsoft edge"],
        "windows": ["msedge"],
        "mac":     ["app:Microsoft Edge"],
        "linux":   ["microsoft-edge", "microsoft-edge-stable"],
    },
    "safari": {
        "aliases": ["safari"],
        "windows": [],
        "mac":     ["app:Safari"],
        "linux":   [],
    },
    "brave": {
        "aliases": ["brave", "brave browser"],
        "windows": ["brave"],
        "mac":     ["app:Brave Browser"],
        "linux":   ["brave-browser", "brave"],
    },
    "opera": {
        "aliases": ["opera"],
        "windows": ["opera"],
        "mac":     ["app:Opera"],
        "linux":   ["opera"],
    },
    "vivaldi": {
        "aliases": ["vivaldi"],
        "windows": ["vivaldi"],
        "mac":     ["app:Vivaldi"],
        "linux":   ["vivaldi", "vivaldi-stable"],
    },
    "tor": {
        "aliases": ["tor", "tor browser"],
        "windows": ["tor browser"],
        "mac":     ["app:Tor Browser"],
        "linux":   ["torbrowser-launcher", "tor-browser"],
    },
    "arc": {
        "aliases": ["arc", "arc browser"],
        "windows": [],
        "mac":     ["app:Arc"],
        "linux":   [],
    },

    # ── Terminals & editors ───────────────────────────────────────────────────
    "terminal": {
        "aliases": ["terminal", "windows terminal", "cmd", "command prompt", "powershell", "shell"],
        "windows": ["wt", "powershell", "cmd"],
        "mac":     ["app:Terminal", "app:iTerm"],
        "linux":   ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm",
                    "alacritty", "kitty", "tilix"],
    },
    "warp": {
        "aliases": ["warp", "warp terminal"],
        "windows": ["warp"],
        "mac":     ["app:Warp"],
        "linux":   ["warp"],
    },
    "hyper": {
        "aliases": ["hyper", "hyper terminal"],
        "windows": ["hyper"],
        "mac":     ["app:Hyper"],
        "linux":   ["hyper"],
    },
    "vscode": {
        "aliases": ["vscode", "vs code", "visual studio code", "code"],
        "windows": ["code"],
        "mac":     ["app:Visual Studio Code", "code"],
        "linux":   ["code", "codium"],
    },
    "cursor": {
        "aliases": ["cursor", "cursor editor"],
        "windows": ["cursor"],
        "mac":     ["app:Cursor"],
        "linux":   ["cursor"],
    },
    "sublime": {
        "aliases": ["sublime", "sublime text"],
        "windows": ["subl"],
        "mac":     ["app:Sublime Text", "subl"],
        "linux":   ["subl", "sublime-text"],
    },
    "atom": {
        "aliases": ["atom"],
        "windows": ["atom"],
        "mac":     ["app:Atom"],
        "linux":   ["atom"],
    },
    "notepad": {
        "aliases": ["notepad", "text editor"],
        "windows": ["notepad"],
        "mac":     ["app:TextEdit"],
        "linux":   ["gedit", "kate", "mousepad", "xed", "leafpad", "geany"],
    },
    "vim": {
        "aliases": ["vim", "gvim"],
        "windows": ["gvim", "vim"],
        "mac":     ["app:MacVim", "mvim"],
        "linux":   ["gvim", "vim"],
    },
    "emacs": {
        "aliases": ["emacs"],
        "windows": ["emacs", "runemacs"],
        "mac":     ["app:Emacs"],
        "linux":   ["emacs"],
    },
    "nano": {
        "aliases": ["nano"],
        "windows": [],
        "mac":     [],
        "linux":   ["xterm -e nano"],
    },
    "visual_studio": {
        "aliases": ["visual studio", "vs", "devenv"],
        "windows": ["devenv"],
        "mac":     [],
        "linux":   [],
    },
    "xcode": {
        "aliases": ["xcode"],
        "windows": [],
        "mac":     ["app:Xcode"],
        "linux":   [],
    },

    # ── IDEs ─────────────────────────────────────────────────────────────────
    "pycharm": {
        "aliases": ["pycharm", "py charm"],
        "windows": ["pycharm", "pycharm64"],
        "mac":     ["app:PyCharm", "app:PyCharm CE"],
        "linux":   ["pycharm", "pycharm-community", "pycharm.sh"],
    },
    "intellij": {
        "aliases": ["intellij", "intellij idea", "idea"],
        "windows": ["idea64"],
        "mac":     ["app:IntelliJ IDEA", "app:IntelliJ IDEA CE"],
        "linux":   ["idea", "intellij-idea-community"],
    },
    "webstorm": {
        "aliases": ["webstorm"],
        "windows": ["webstorm64"],
        "mac":     ["app:WebStorm"],
        "linux":   ["webstorm"],
    },
    "android_studio": {
        "aliases": ["android studio"],
        "windows": ["studio64"],
        "mac":     ["app:Android Studio"],
        "linux":   ["studio", "android-studio"],
    },
    "eclipse": {
        "aliases": ["eclipse"],
        "windows": ["eclipse"],
        "mac":     ["app:Eclipse"],
        "linux":   ["eclipse"],
    },
    "netbeans": {
        "aliases": ["netbeans"],
        "windows": ["netbeans64"],
        "mac":     ["app:NetBeans"],
        "linux":   ["netbeans"],
    },
    "rider": {
        "aliases": ["rider", "jetbrains rider"],
        "windows": ["rider64"],
        "mac":     ["app:Rider"],
        "linux":   ["rider"],
    },
    "clion": {
        "aliases": ["clion"],
        "windows": ["clion64"],
        "mac":     ["app:CLion"],
        "linux":   ["clion"],
    },
    "datagrip": {
        "aliases": ["datagrip"],
        "windows": ["datagrip64"],
        "mac":     ["app:DataGrip"],
        "linux":   ["datagrip"],
    },
    "goland": {
        "aliases": ["goland"],
        "windows": ["goland64"],
        "mac":     ["app:GoLand"],
        "linux":   ["goland"],
    },
    "rubymine": {
        "aliases": ["rubymine"],
        "windows": ["rubymine64"],
        "mac":     ["app:RubyMine"],
        "linux":   ["rubymine"],
    },

    # ── Dev tools ─────────────────────────────────────────────────────────────
    "postman": {
        "aliases": ["postman"],
        "windows": ["postman"],
        "mac":     ["app:Postman"],
        "linux":   ["postman"],
    },
    "insomnia": {
        "aliases": ["insomnia"],
        "windows": ["insomnia"],
        "mac":     ["app:Insomnia"],
        "linux":   ["insomnia"],
    },
    "dbeaver": {
        "aliases": ["dbeaver", "db beaver"],
        "windows": ["dbeaver"],
        "mac":     ["app:DBeaver"],
        "linux":   ["dbeaver"],
    },
    "tableplus": {
        "aliases": ["tableplus", "table plus"],
        "windows": ["tableplus"],
        "mac":     ["app:TablePlus"],
        "linux":   ["tableplus"],
    },
    "sequel_pro": {
        "aliases": ["sequel pro", "sequelpro"],
        "windows": [],
        "mac":     ["app:Sequel Pro", "app:Sequel Ace"],
        "linux":   [],
    },
    "github_desktop": {
        "aliases": ["github desktop", "github"],
        "windows": ["githubdesktop"],
        "mac":     ["app:GitHub Desktop"],
        "linux":   ["github-desktop"],
    },
    "gitkraken": {
        "aliases": ["gitkraken", "git kraken"],
        "windows": ["gitkraken"],
        "mac":     ["app:GitKraken"],
        "linux":   ["gitkraken"],
    },
    "sourcetree": {
        "aliases": ["sourcetree", "source tree"],
        "windows": ["sourcetree"],
        "mac":     ["app:Sourcetree"],
        "linux":   [],
    },
    "docker_desktop": {
        "aliases": ["docker", "docker desktop"],
        "windows": ["docker desktop"],
        "mac":     ["app:Docker"],
        "linux":   ["docker", "xdg-open:https://docs.docker.com/desktop/install/linux-install/"],
    },
    "figma": {
        "aliases": ["figma"],
        "windows": ["figma"],
        "mac":     ["app:Figma"],
        "linux":   ["figma-linux", "xdg-open:https://figma.com"],
    },

    # ── Communication ─────────────────────────────────────────────────────────
    "slack": {
        "aliases": ["slack"],
        "windows": ["slack"],
        "mac":     ["app:Slack"],
        "linux":   ["slack"],
    },
    "zoom": {
        "aliases": ["zoom", "zoom meeting"],
        "windows": ["zoom"],
        "mac":     ["app:zoom.us", "app:Zoom"],
        "linux":   ["zoom", "zoom-client"],
    },
    "teams": {
        "aliases": ["teams", "microsoft teams"],
        "windows": ["teams", "ms-teams:"],
        "mac":     ["app:Microsoft Teams"],
        "linux":   ["teams-for-linux", "microsoft-teams"],
    },
    "discord": {
        "aliases": ["discord"],
        "windows": ["discord"],
        "mac":     ["app:Discord"],
        "linux":   ["discord"],
    },
    "signal": {
        "aliases": ["signal"],
        "windows": ["signal"],
        "mac":     ["app:Signal"],
        "linux":   ["signal-desktop"],
    },
    "whatsapp": {
        "aliases": ["whatsapp", "whats app"],
        "windows": ["whatsapp"],
        "mac":     ["app:WhatsApp"],
        "linux":   ["whatsapp-desktop", "xdg-open:https://web.whatsapp.com"],
    },
    "telegram_desktop": {
        "aliases": ["telegram", "telegram desktop"],
        "windows": ["telegram"],
        "mac":     ["app:Telegram"],
        "linux":   ["telegram-desktop", "telegram"],
    },
    "skype": {
        "aliases": ["skype"],
        "windows": ["skype"],
        "mac":     ["app:Skype"],
        "linux":   ["skypeforlinux"],
    },
    "viber": {
        "aliases": ["viber"],
        "windows": ["viber"],
        "mac":     ["app:Viber"],
        "linux":   ["viber"],
    },
    "messages": {
        "aliases": ["messages", "imessage"],
        "windows": [],
        "mac":     ["app:Messages"],
        "linux":   ["xdg-open:https://messages.google.com"],
    },
    "facetime": {
        "aliases": ["facetime", "face time"],
        "windows": [],
        "mac":     ["app:FaceTime"],
        "linux":   [],
    },
    "outlook": {
        "aliases": ["outlook", "microsoft outlook", "mail"],
        "windows": ["outlook"],
        "mac":     ["app:Microsoft Outlook", "app:Mail"],
        "linux":   ["thunderbird", "evolution", "geary"],
    },
    "thunderbird": {
        "aliases": ["thunderbird", "mozilla thunderbird"],
        "windows": ["thunderbird"],
        "mac":     ["app:Thunderbird"],
        "linux":   ["thunderbird"],
    },

    # ── Productivity & office ─────────────────────────────────────────────────
    "office_word": {
        "aliases": ["word", "microsoft word"],
        "windows": ["winword"],
        "mac":     ["app:Microsoft Word"],
        "linux":   ["libreoffice --writer", "lowriter"],
    },
    "office_excel": {
        "aliases": ["excel", "microsoft excel", "spreadsheet"],
        "windows": ["excel"],
        "mac":     ["app:Microsoft Excel"],
        "linux":   ["libreoffice --calc", "localc"],
    },
    "office_powerpoint": {
        "aliases": ["powerpoint", "microsoft powerpoint", "presentation"],
        "windows": ["powerpnt"],
        "mac":     ["app:Microsoft PowerPoint"],
        "linux":   ["libreoffice --impress", "loimpress"],
    },
    "libreoffice": {
        "aliases": ["libreoffice", "libre office"],
        "windows": ["soffice"],
        "mac":     ["app:LibreOffice"],
        "linux":   ["libreoffice", "soffice"],
    },
    "pages": {
        "aliases": ["pages"],
        "windows": [],
        "mac":     ["app:Pages"],
        "linux":   [],
    },
    "numbers": {
        "aliases": ["numbers"],
        "windows": [],
        "mac":     ["app:Numbers"],
        "linux":   [],
    },
    "keynote": {
        "aliases": ["keynote"],
        "windows": [],
        "mac":     ["app:Keynote"],
        "linux":   [],
    },
    "notion": {
        "aliases": ["notion"],
        "windows": ["notion"],
        "mac":     ["app:Notion"],
        "linux":   ["notion-app", "xdg-open:https://notion.so"],
    },
    "obsidian": {
        "aliases": ["obsidian"],
        "windows": ["obsidian"],
        "mac":     ["app:Obsidian"],
        "linux":   ["obsidian"],
    },

    # ── Cloud storage ─────────────────────────────────────────────────────────
    "dropbox": {
        "aliases": ["dropbox"],
        "windows": ["dropbox"],
        "mac":     ["app:Dropbox"],
        "linux":   ["dropbox"],
    },
    "onedrive": {
        "aliases": ["onedrive", "one drive"],
        "windows": ["onedrive"],
        "mac":     ["app:OneDrive"],
        "linux":   ["onedrive", "xdg-open:https://onedrive.live.com"],
    },
    "google_drive": {
        "aliases": ["google drive", "drive"],
        "windows": ["googledrivefs"],
        "mac":     ["app:Google Drive"],
        "linux":   ["xdg-open:https://drive.google.com"],
    },

    # ── Media ─────────────────────────────────────────────────────────────────
    "vlc": {
        "aliases": ["vlc", "vlc media player"],
        "windows": ["vlc"],
        "mac":     ["app:VLC"],
        "linux":   ["vlc"],
    },
    "spotify": {
        "aliases": ["spotify"],
        "windows": ["spotify"],
        "mac":     ["app:Spotify"],
        "linux":   ["spotify"],
    },
    "music": {
        "aliases": ["music", "apple music", "itunes"],
        "windows": [],
        "mac":     ["app:Music"],
        "linux":   ["rhythmbox", "banshee", "clementine", "xdg-open:https://music.apple.com"],
    },
    "podcasts": {
        "aliases": ["podcasts"],
        "windows": [],
        "mac":     ["app:Podcasts"],
        "linux":   ["gpodder", "xdg-open:https://podcasts.apple.com"],
    },
    "windows_media_player": {
        "aliases": ["windows media player", "media player"],
        "windows": ["wmplayer", "ms-windows-media:"],
        "mac":     [],
        "linux":   [],
    },
    "gimp": {
        "aliases": ["gimp", "image editor"],
        "windows": ["gimp"],
        "mac":     ["app:GIMP"],
        "linux":   ["gimp"],
    },
    "inkscape": {
        "aliases": ["inkscape", "vector editor"],
        "windows": ["inkscape"],
        "mac":     ["app:Inkscape"],
        "linux":   ["inkscape"],
    },
    "audacity": {
        "aliases": ["audacity", "audio editor"],
        "windows": ["audacity"],
        "mac":     ["app:Audacity"],
        "linux":   ["audacity"],
    },
    "blender": {
        "aliases": ["blender", "3d editor"],
        "windows": ["blender"],
        "mac":     ["app:Blender"],
        "linux":   ["blender"],
    },
    "obs": {
        "aliases": ["obs", "obs studio", "screen recorder"],
        "windows": ["obs64", "obs"],
        "mac":     ["app:OBS"],
        "linux":   ["obs"],
    },
    "handbrake": {
        "aliases": ["handbrake", "video converter"],
        "windows": ["handbrake"],
        "mac":     ["app:HandBrake"],
        "linux":   ["ghb"],
    },
    "kdenlive": {
        "aliases": ["kdenlive", "video editor"],
        "windows": ["kdenlive"],
        "mac":     ["app:Kdenlive"],
        "linux":   ["kdenlive"],
    },
    "davinci": {
        "aliases": ["davinci", "davinci resolve", "resolve"],
        "windows": ["resolve"],
        "mac":     ["app:DaVinci Resolve"],
        "linux":   ["resolve"],
    },
    "preview": {
        "aliases": ["preview"],
        "windows": [],
        "mac":     ["app:Preview"],
        "linux":   [],
    },
    "paint": {
        "aliases": ["paint", "mspaint", "drawing"],
        "windows": ["mspaint"],
        "mac":     ["app:Preview"],
        "linux":   ["pinta", "kolourpaint", "drawing"],
    },

    # ── Gaming ────────────────────────────────────────────────────────────────
    "steam": {
        "aliases": ["steam"],
        "windows": ["steam"],
        "mac":     ["app:Steam"],
        "linux":   ["steam"],
    },
    "epic_games": {
        "aliases": ["epic games", "epic games launcher", "epic"],
        "windows": ["epicgameslauncher"],
        "mac":     ["app:Epic Games Launcher"],
        "linux":   ["legendary", "xdg-open:https://store.epicgames.com"],
    },
    "xbox": {
        "aliases": ["xbox", "xbox app"],
        "windows": ["ms-xbox:"],
        "mac":     [],
        "linux":   [],
    },

    # ── Security ──────────────────────────────────────────────────────────────
    "bitwarden": {
        "aliases": ["bitwarden"],
        "windows": ["bitwarden"],
        "mac":     ["app:Bitwarden"],
        "linux":   ["bitwarden"],
    },
    "onepassword": {
        "aliases": ["1password", "one password"],
        "windows": ["1password"],
        "mac":     ["app:1Password"],
        "linux":   ["1password"],
    },
    "windows_security": {
        "aliases": ["windows security", "windows defender", "defender", "antivirus"],
        "windows": ["windowsdefender:"],
        "mac":     [],
        "linux":   [],
    },

    # ── Utilities ─────────────────────────────────────────────────────────────
    "file_manager": {
        "aliases": ["explorer", "file explorer", "finder", "files", "file manager"],
        "windows": ["explorer"],
        "mac":     ["app:Finder"],
        "linux":   ["nautilus", "dolphin", "thunar", "nemo", "caja", "pcmanfm",
                    "xdg-open:~"],
    },
    "archive_manager": {
        "aliases": ["archive manager", "7zip", "7-zip", "unarchiver", "zip", "winrar"],
        "windows": ["7zFM"],
        "mac":     ["app:The Unarchiver", "app:Archive Utility"],
        "linux":   ["file-roller", "ark", "xarchiver", "engrampa"],
    },
    "calculator": {
        "aliases": ["calculator", "calc"],
        "windows": ["calc"],
        "mac":     ["app:Calculator"],
        "linux":   ["gnome-calculator", "kcalc", "qalculate-gtk", "galculator"],
    },
    "notes": {
        "aliases": ["sticky notes", "sticky note", "microsoft sticky notes", "windows sticky notes",
                    "stickies", "notes"],
        "windows": [STICKY_NOTES_TARGET],
        "mac":     ["app:Stickies", "app:Notes"],
        "linux":   ["xpad", "indicator-stickynotes", "gnote", "tomboy"],
    },
    "clock": {
        "aliases": ["clock", "alarms", "alarms and clock"],
        "windows": ["ms-clock:"],
        "mac":     ["app:Clock"],
        "linux":   ["gnome-clocks", "kclock"],
    },
    "calendar": {
        "aliases": ["calendar", "ical"],
        "windows": ["outlookcal:"],
        "mac":     ["app:Calendar"],
        "linux":   ["gnome-calendar", "korganizer"],
    },
    "reminders": {
        "aliases": ["reminders"],
        "windows": ["ms-todo:"],
        "mac":     ["app:Reminders"],
        "linux":   ["gnome-todo", "planner"],
    },
    "contacts": {
        "aliases": ["contacts", "address book"],
        "windows": ["ms-people:"],
        "mac":     ["app:Contacts"],
        "linux":   ["gnome-contacts", "kaddressbook"],
    },
    "maps": {
        "aliases": ["maps", "map"],
        "windows": ["bingmaps:"],
        "mac":     ["app:Maps"],
        "linux":   ["xdg-open:https://maps.google.com"],
    },
    "camera": {
        "aliases": ["camera", "webcam", "photo booth"],
        "windows": ["microsoft.windows.camera:"],
        "mac":     ["app:Photo Booth"],
        "linux":   ["cheese", "kamoso", "guvcview"],
    },
    "photos": {
        "aliases": ["photos", "pictures", "image viewer"],
        "windows": ["ms-photos:"],
        "mac":     ["app:Photos", "app:Preview"],
        "linux":   ["eog", "gwenview", "ristretto", "nomacs", "shotwell"],
    },
    "books": {
        "aliases": ["books", "ebooks", "reading"],
        "windows": ["ms-read:"],
        "mac":     ["app:Books"],
        "linux":   ["calibre", "foliate", "evince"],
    },
    "pdf_reader": {
        "aliases": ["pdf", "pdf reader", "acrobat"],
        "windows": ["AcroRd32", "acrord32"],
        "mac":     ["app:Preview", "app:Adobe Acrobat"],
        "linux":   ["evince", "okular", "xreader", "atril"],
    },
    "virtualbox": {
        "aliases": ["virtualbox", "virtual box", "vm"],
        "windows": ["virtualbox"],
        "mac":     ["app:VirtualBox"],
        "linux":   ["virtualbox"],
    },
    "vmware": {
        "aliases": ["vmware", "vmware workstation", "vmware fusion"],
        "windows": ["vmware"],
        "mac":     ["app:VMware Fusion"],
        "linux":   ["vmware"],
    },

    # ── System settings & tools ───────────────────────────────────────────────
    "settings": {
        "aliases": ["settings", "system settings", "preferences", "system preferences"],
        "windows": ["ms-settings:"],
        "mac":     ["app:System Settings", "app:System Preferences"],
        "linux":   ["gnome-control-center", "systemsettings", "xfce4-settings-manager",
                    "cinnamon-settings", "mate-control-center"],
    },
    "display_settings": {
        "aliases": ["display settings", "screen resolution", "display", "resolution"],
        "windows": ["ms-settings:display"],
        "mac":     ["app:System Settings"],
        "linux":   ["xrandr", "arandr", "gnome-control-center display"],
    },
    "sound_settings": {
        "aliases": ["sound settings", "audio settings", "sound"],
        "windows": ["ms-settings:sound"],
        "mac":     ["app:System Settings"],
        "linux":   ["pavucontrol", "gnome-control-center sound"],
    },
    "bluetooth_settings": {
        "aliases": ["bluetooth", "bluetooth settings"],
        "windows": ["ms-settings:bluetooth"],
        "mac":     ["app:System Settings"],
        "linux":   ["blueman-manager", "gnome-control-center bluetooth"],
    },
    "network_settings": {
        "aliases": ["network", "network settings", "wifi", "wi-fi"],
        "windows": ["ms-settings:network"],
        "mac":     ["app:System Settings"],
        "linux":   ["nm-connection-editor", "gnome-control-center network"],
    },
    "update_settings": {
        "aliases": ["windows update", "software update", "updates"],
        "windows": ["ms-settings:windowsupdate"],
        "mac":     ["app:System Settings"],
        "linux":   ["gnome-software", "plasma-discover"],
    },
    "privacy_settings": {
        "aliases": ["privacy settings", "privacy"],
        "windows": ["ms-settings:privacy"],
        "mac":     ["app:System Settings"],
        "linux":   ["gnome-control-center privacy"],
    },
    "accessibility": {
        "aliases": ["accessibility", "ease of access"],
        "windows": ["ms-settings:easeofaccess"],
        "mac":     ["app:System Settings"],
        "linux":   ["gnome-control-center universal-access"],
    },
    "task_manager": {
        "aliases": ["task manager", "activity monitor", "system monitor"],
        "windows": ["taskmgr"],
        "mac":     ["app:Activity Monitor"],
        "linux":   ["gnome-system-monitor", "ksysguard", "mate-system-monitor",
                    "xfce4-taskmanager"],
    },
    "resource_monitor": {
        "aliases": ["resource monitor", "resmon", "performance monitor"],
        "windows": ["resmon", "perfmon"],
        "mac":     ["app:Activity Monitor"],
        "linux":   ["gnome-system-monitor", "ksysguard"],
    },
    "event_viewer": {
        "aliases": ["event viewer", "event log"],
        "windows": ["eventvwr"],
        "mac":     ["app:Console"],
        "linux":   ["gnome-logs"],
    },
    "device_manager": {
        "aliases": ["device manager"],
        "windows": ["devmgmt.msc"],
        "mac":     [],
        "linux":   [],
    },
    "registry_editor": {
        "aliases": ["registry editor", "regedit", "registry"],
        "windows": ["regedit"],
        "mac":     [],
        "linux":   [],
    },
    "disk_management": {
        "aliases": ["disk management", "disk manager"],
        "windows": ["diskmgmt.msc"],
        "mac":     ["app:Disk Utility"],
        "linux":   ["gparted", "gnome-disks"],
    },
    "disk_utility": {
        "aliases": ["disk utility"],
        "windows": ["diskmgmt.msc"],
        "mac":     ["app:Disk Utility"],
        "linux":   ["gnome-disks", "gparted"],
    },
    "task_scheduler": {
        "aliases": ["task scheduler"],
        "windows": ["taskschd.msc"],
        "mac":     [],
        "linux":   [],
    },
    "snipping": {
        "aliases": ["snipping tool", "screenshot tool", "screenshots"],
        "windows": ["SnippingTool", "ms-screenclip:"],
        "mac":     ["app:Screenshot"],
        "linux":   ["gnome-screenshot", "flameshot", "spectacle", "xfce4-screenshooter",
                    "scrot"],
    },
    "store": {
        "aliases": ["store", "microsoft store", "app store", "software centre"],
        "windows": ["ms-windows-store:"],
        "mac":     ["app:App Store"],
        "linux":   ["gnome-software", "plasma-discover", "snap-store"],
    },
    "control_panel": {
        "aliases": ["control panel"],
        "windows": ["control"],
        "mac":     ["app:System Settings"],
        "linux":   ["gnome-control-center"],
    },
    "keychain_access": {
        "aliases": ["keychain", "keychain access"],
        "windows": ["certmgr.msc"],
        "mac":     ["app:Keychain Access"],
        "linux":   ["seahorse"],
    },
    "script_editor": {
        "aliases": ["script editor", "applescript"],
        "windows": [],
        "mac":     ["app:Script Editor"],
        "linux":   [],
    },
    "automator": {
        "aliases": ["automator"],
        "windows": [],
        "mac":     ["app:Automator"],
        "linux":   [],
    },
    "console": {
        "aliases": ["console", "log viewer"],
        "windows": ["eventvwr"],
        "mac":     ["app:Console"],
        "linux":   ["gnome-logs"],
    },
    "font_book": {
        "aliases": ["font book", "fonts", "font viewer"],
        "windows": ["fontview"],
        "mac":     ["app:Font Book"],
        "linux":   ["gnome-font-viewer", "font-manager"],
    },
    "voice_memos": {
        "aliases": ["voice memos", "voice recorder"],
        "windows": ["ms-soundrecorder:"],
        "mac":     ["app:Voice Memos"],
        "linux":   ["gnome-sound-recorder"],
    },
    "news": {
        "aliases": ["news"],
        "windows": ["bingnews:"],
        "mac":     ["app:News"],
        "linux":   ["xdg-open:https://news.google.com"],
    },
    "stocks": {
        "aliases": ["stocks"],
        "windows": ["xdg-open:https://finance.yahoo.com"],
        "mac":     ["app:Stocks"],
        "linux":   ["xdg-open:https://finance.yahoo.com"],
    },
    "find_my": {
        "aliases": ["find my", "find my iphone", "find my mac"],
        "windows": [],
        "mac":     ["app:Find My"],
        "linux":   [],
    },
    "paint_3d": {
        "aliases": ["paint 3d", "3d paint"],
        "windows": ["ms-paint:"],
        "mac":     [],
        "linux":   [],
    },
    "mixed_reality": {
        "aliases": ["mixed reality portal", "vr"],
        "windows": ["ms-holographicfirstrun:"],
        "mac":     [],
        "linux":   [],
    },
}


# ── Windows-only alias fast path ──────────────────────────────────────────────

COMMON_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "brave": "brave",
    "opera": "opera",
    "vivaldi": "vivaldi",
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
    "cursor": "cursor",
    "sublime": "subl",
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
    "registry editor": "regedit",
    "regedit": "regedit",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "event viewer": "eventvwr",
    "task scheduler": "taskschd.msc",
    "resource monitor": "resmon",
    "vlc": "vlc",
    "zoom": "zoom",
    "slack": "slack",
    "signal": "signal",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "steam": "steam",
    "gimp": "gimp",
    "blender": "blender",
    "obs": "obs64",
    "postman": "postman",
    "docker": "docker desktop",
}

STICKY_NOTES_APP_IDS = [
    "Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App",
]

STICKY_NOTES_PROTOCOLS = [
    "ms-sticky-notes:",
]


# ── Windows discovery ─────────────────────────────────────────────────────────

def _get_luna_apps() -> dict[str, str]:
    apps = {}
    if LUNA_APPS_DIR.exists():
        for lnk in LUNA_APPS_DIR.glob("*.lnk"):
            apps[lnk.stem.lower()] = str(lnk)
    return apps


def _get_start_menu_apps() -> dict[str, str]:
    apps = {}
    search_dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for lnk in d.rglob("*.lnk"):
            apps[lnk.stem.lower()] = str(lnk)
    return apps


@lru_cache(maxsize=1)
def _get_registry_apps() -> dict[str, str]:
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
                    sub_key  = winreg.OpenKey(key, sub_name)
                    path, _  = winreg.QueryValueEx(sub_key, "")
                    apps[sub_name.lower().replace(".exe", "")] = path
                except Exception:
                    continue
        except Exception:
            continue
    return apps


@lru_cache(maxsize=1)
def _get_store_apps() -> dict[str, str]:
    apps = {}
    if not IS_WINDOWS:
        return apps
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | ForEach-Object { \"$($_.Name)`t$($_.AppID)\" }"],
            capture_output=True, text=True, timeout=8,
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


# ── macOS discovery ───────────────────────────────────────────────────────────

def _spotlight_search(name: str) -> str | None:
    """Find a .app bundle on macOS via mdfind (Spotlight)."""
    if not IS_MAC:
        return None
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", "/Applications",
             f'kMDItemKind == "Application" && kMDItemDisplayName == "{name}"'],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if lines:
                return f"app_path:{lines[0]}"
    except Exception:
        pass
    # Fallback: partial name search
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", "/Applications", f'kMDItemDisplayName == "*{name}*"cdw'],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if lines:
                return f"app_path:{lines[0]}"
    except Exception:
        pass
    return None


# ── Linux discovery ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_desktop_apps() -> dict[str, str]:
    """Parse XDG .desktop files from standard application directories."""
    if not IS_LINUX:
        return {}
    apps: dict[str, str] = {}
    search_dirs = [
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
        Path("/var/lib/snapd/desktop/applications"),
    ]
    _bad_tokens = {"%u", "%U", "%f", "%F", "%d", "%D", "%n", "%N", "%i", "%m", "%k", "%v", "%c"}

    for directory in search_dirs:
        if not directory.exists():
            continue
        for desktop_file in directory.glob("*.desktop"):
            try:
                name: str | None = None
                exec_cmd: str | None = None
                skip = False
                with open(desktop_file, encoding="utf-8", errors="ignore") as fh:
                    in_entry = False
                    for line in fh:
                        line = line.strip()
                        if line == "[Desktop Entry]":
                            in_entry = True
                        elif line.startswith("[") and in_entry:
                            break
                        elif in_entry:
                            if line.startswith("NoDisplay=true") or line.startswith("Hidden=true"):
                                skip = True
                                break
                            if line.startswith("Type=") and not line.startswith("Type=Application"):
                                skip = True
                                break
                            if line.startswith("Name=") and name is None:
                                name = line[5:].strip()
                            if line.startswith("Exec=") and exec_cmd is None:
                                parts = line[5:].strip().split()
                                # Strip desktop-file field codes and leading env vars
                                clean = [p for p in parts if p not in _bad_tokens
                                         and not p.startswith("%")]
                                if clean:
                                    exec_cmd = clean[0]
                if not skip and name and exec_cmd:
                    apps[_normalize(name)] = exec_cmd
            except Exception:
                continue
    return apps


# ── Shared helpers ────────────────────────────────────────────────────────────

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
        aliases = {_normalize(a) for a in profile["aliases"]}
        if query in aliases or any(query in a or a in query for a in aliases):
            targets = list(profile.get(_platform_key(), []))
            return [t for t in targets if t]  # drop empty strings
    return []


def _first_available_target(targets: list[str]) -> str | None:
    if not targets:
        return None
    if IS_MAC:
        return targets[0]
    if IS_WINDOWS:
        for t in targets:
            if (t == STICKY_NOTES_TARGET or t.endswith(":")
                    or t.startswith("ms-") or t.startswith("shell:")):
                return t
            if shutil.which(t.split()[0]):
                return t
        return targets[0]
    # Linux
    for t in targets:
        if t.startswith("xdg-open:"):
            return t
        if shutil.which(t.split()[0]):
            return t
    return targets[0]


def _best_match(query: str, apps: dict[str, str]) -> str | None:
    if query in apps:
        return apps[query]
    for k, v in apps.items():
        if query in k or k in query:
            return v
    close = get_close_matches(query, apps.keys(), n=1, cutoff=0.72)
    if close:
        return apps[close[0]]
    return None


# ── Sticky Notes (Windows only) ───────────────────────────────────────────────

def _sticky_notes_candidates() -> list[str]:
    candidates: list[str] = []
    for apps in (_get_store_apps(), _get_start_menu_apps(), _get_luna_apps()):
        for app_name, target in apps.items():
            n = _normalize(app_name)
            if n in {"sticky notes", "microsoft sticky notes"}:
                candidates.insert(0, target)
            elif "sticky" in n and "note" in n:
                candidates.append(target)
    candidates.extend(f"shell:AppsFolder\\{app_id}" for app_id in STICKY_NOTES_APP_IDS)
    candidates.extend(STICKY_NOTES_PROTOCOLS)
    deduped: list[str] = []
    for c in candidates:
        if c and c not in deduped:
            deduped.append(c)
    return deduped


# ── Target launchers ──────────────────────────────────────────────────────────

def _launch_target(target: str) -> None:
    # macOS open -a
    if target.startswith("app:"):
        app_name = target[4:]
        if IS_MAC:
            subprocess.Popen(["open", "-a", app_name])
            return
        raise OSError(f"app: target only supported on macOS: {app_name}")

    # macOS full .app path found via Spotlight
    if target.startswith("app_path:"):
        path = target[9:]
        if IS_MAC:
            subprocess.Popen(["open", path])
            return
        raise OSError(f"app_path: target only supported on macOS: {path}")

    # Linux xdg-open URI
    if target.startswith("xdg-open:"):
        uri = target[9:]
        if uri == "~":
            uri = str(Path.home())
        if IS_LINUX:
            subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return
        raise OSError(f"xdg-open: target only supported on Linux: {uri}")

    # Windows URI schemes, .lnk, .msc, full paths
    if (target.endswith(":") or target.startswith("ms-") or target.startswith("shell:")
            or target.endswith(".lnk") or target.endswith(".msc")):
        if IS_WINDOWS:
            os.startfile(target)
            return
        raise OSError(f"Windows-only target on non-Windows: {target}")

    if Path(target).exists():
        if IS_WINDOWS:
            os.startfile(target)
        else:
            subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if IS_WINDOWS:
        subprocess.Popen([target], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return

    subprocess.Popen(target.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── Sticky Notes launcher ─────────────────────────────────────────────────────

def launch_sticky_notes() -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Sticky Notes is only available on Windows."
    errors = []
    for target in _sticky_notes_candidates():
        try:
            _launch_target(target)
            return True, "Opened Sticky Notes"
        except Exception as e:
            errors.append(f"{target}: {e}")
    return (
        False,
        "Couldn't open Sticky Notes. Install it from the Microsoft Store or add a shortcut "
        "to data/apps/Sticky Notes.lnk.",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def find_app(name: str) -> tuple[bool, str]:
    """
    Locate an application by name.
    Returns (found: bool, launch_target: str).
    """
    query = _normalize(name)

    # 1. Curated profile
    profile_target = _first_available_target(_profile_targets(query))
    if profile_target:
        return True, profile_target

    # 2. PATH shortcut (all platforms)
    if shutil.which(query):
        return True, query

    # 3. macOS Spotlight — find any installed .app
    if IS_MAC:
        spotlight = _spotlight_search(name)
        if spotlight:
            return True, spotlight
        return True, f"app:{name}"

    # 4. Linux .desktop catalogue
    if IS_LINUX:
        desktop_apps = _get_desktop_apps()
        target = _best_match(query, desktop_apps)
        if target:
            return True, target
        return False, f"No application found matching '{name}' on this Linux system."

    # 5. Windows alias fast path
    if query in COMMON_APP_ALIASES:
        return True, COMMON_APP_ALIASES[query]
    for alias, target in COMMON_APP_ALIASES.items():
        if query in alias or alias in query:
            return True, target

    # 6. Windows registry / Start Menu / Store
    for apps in (_get_luna_apps(), _get_registry_apps(), _get_start_menu_apps(), _get_store_apps()):
        target = _best_match(query, apps)
        if target:
            return True, target

    # 7. Final Windows fallback — let ShellExecute try
    return True, query


def launch_app(name: str) -> tuple[bool, str]:
    """Launch an application by name. Returns (success, message)."""
    found, target = find_app(name)
    if not found:
        return False, f"Couldn't find an app matching '{name}' on this platform."

    if target == STICKY_NOTES_TARGET:
        return launch_sticky_notes()

    try:
        _launch_target(target)
        return True, f"Launched {name}"
    except Exception as e:
        return False, f"Couldn't launch '{name}': {e}"


def list_known_apps() -> list[str]:
    """Return a combined list of findable app names for this platform."""
    platform_key = _platform_key()
    names: list[str] = []

    for profile in APP_PROFILES.values():
        if profile.get(platform_key):
            names.extend(profile["aliases"])

    if IS_LINUX:
        names.extend(_get_desktop_apps().keys())
    elif IS_WINDOWS:
        names.extend(COMMON_APP_ALIASES.keys())
        names.extend(_get_registry_apps().keys())
        names.extend(_get_start_menu_apps().keys())
        names.extend(_get_store_apps().keys())
        if _sticky_notes_candidates():
            names += ["sticky notes", "microsoft sticky notes"]

    return sorted(set(names))


def list_app_profiles() -> dict:
    """Return curated app profile metadata for UI / debug views."""
    platform_key = _platform_key()
    profiles = [
        {
            "id": app_id,
            "aliases": profile["aliases"],
            "platform": platform_key,
            "targets": [t for t in profile.get(platform_key, []) if t],
            "supported": bool(profile.get(platform_key)),
        }
        for app_id, profile in APP_PROFILES.items()
    ]
    return {"platform": PLATFORM, "profiles": profiles}
