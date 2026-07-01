from __future__ import annotations

import sys

VK_CONTROL = 0x11
VK_C = 0x43
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def send_ctrl_key(vk: int) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.windll.user32
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def send_ctrl_c() -> None:
    send_ctrl_key(VK_C)


def send_ctrl_v() -> None:
    send_ctrl_key(VK_V)
