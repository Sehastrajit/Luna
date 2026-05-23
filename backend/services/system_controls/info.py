"""System information."""
from pathlib import Path

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, PLATFORM, _run, _ps


def get_system_info() -> dict:
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
