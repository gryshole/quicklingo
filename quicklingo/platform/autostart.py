from __future__ import annotations

import sys
from pathlib import Path


def _run_key_name() -> str:
    return "QuickLingo"


def autostart_supported() -> bool:
    return sys.platform == "win32"


def is_enabled() -> bool:
    if not autostart_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            value, _ = winreg.QueryValueEx(key, _run_key_name())
            return bool(value)
    except OSError:
        return False


def _executable_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    script = Path(sys.argv[0]).resolve()
    return f'"{sys.executable}" "{script}"'


def set_enabled(enabled: bool) -> None:
    if not autostart_supported():
        return
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(key, _run_key_name(), 0, winreg.REG_SZ, _executable_command())
        else:
            try:
                winreg.DeleteValue(key, _run_key_name())
            except OSError:
                pass
