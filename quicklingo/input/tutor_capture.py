from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from quicklingo.input.tutor_capture_log import log_debug, log_file_path, log_info, log_warning

# Physical left/right modifier keys.
_VK_LCONTROL = 0xA2
_VK_RCONTROL = 0xA3
_VK_LSHIFT = 0xA0
_VK_RSHIFT = 0xA1
_VK_LMENU = 0xA4
_VK_RMENU = 0xA5
_VK_LWIN = 0x5B
_VK_RWIN = 0x5C
_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12
_VK_BACK = 0x08
_VK_RETURN = 0x0D

_MODIFIER_VKS: tuple[tuple[str, int], ...] = (
    ("LCTRL", _VK_LCONTROL),
    ("RCTRL", _VK_RCONTROL),
    ("LSHIFT", _VK_LSHIFT),
    ("RSHIFT", _VK_RSHIFT),
    ("LALT", _VK_LMENU),
    ("RALT", _VK_RMENU),
    ("LWIN", _VK_LWIN),
    ("RWIN", _VK_RWIN),
    ("CTRL", _VK_CONTROL),
    ("ALT", _VK_MENU),
)

_MODIFIER_VK_CODES = frozenset(
    {
        _VK_LCONTROL,
        _VK_RCONTROL,
        _VK_LSHIFT,
        _VK_RSHIFT,
        _VK_LMENU,
        _VK_RMENU,
        _VK_LWIN,
        _VK_RWIN,
        _VK_SHIFT,
        _VK_CONTROL,
        _VK_MENU,
    }
)


def _key_state(vk: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 0, 0
    import ctypes

    user32 = ctypes.windll.user32
    return int(user32.GetAsyncKeyState(vk)), int(user32.GetKeyState(vk))


def _phys_down(vk: int) -> bool:
    async_state, _ = _key_state(vk)
    return bool(async_state & 0x8000)


def _modifiers_physical() -> tuple[bool, bool, bool]:
    ctrl = _phys_down(_VK_LCONTROL) or _phys_down(_VK_RCONTROL)
    alt = _phys_down(_VK_LMENU) or _phys_down(_VK_RMENU)
    win = _phys_down(_VK_LWIN) or _phys_down(_VK_RWIN)
    return ctrl, alt, win


def _modifier_snapshot() -> str:
    parts: list[str] = []
    for name, vk in _MODIFIER_VKS:
        async_state, sync_state = _key_state(vk)
        parts.append(f"{name}:async={async_state:#06x},sync={sync_state:#06x}")
    return " ".join(parts)


def _active_keyboard_layout() -> int:
    """Layout of the foreground window's thread (not the hook thread)."""
    if sys.platform != "win32":
        return 0
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if hwnd:
        thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        return int(user32.GetKeyboardLayout(thread_id))
    return int(user32.GetKeyboardLayout(0))


def _keyboard_layout_id() -> str:
    if sys.platform != "win32":
        return "n/a"
    return f"{_active_keyboard_layout() & 0xFFFF:#06x}"


def _vk_to_typing_char(vk: int) -> tuple[str | None, int]:
    if sys.platform != "win32":
        return None, 0
    import ctypes

    user32 = ctypes.windll.user32
    keyboard_state = (ctypes.c_byte * 256)()
    if _phys_down(_VK_LSHIFT) or _phys_down(_VK_RSHIFT):
        keyboard_state[_VK_SHIFT] = 0x80
    buff = ctypes.create_unicode_buffer(8)
    layout = _active_keyboard_layout()
    result = user32.ToUnicodeEx(
        vk,
        0,
        keyboard_state,
        buff,
        len(buff),
        0,
        layout,
    )
    if result == 1 and buff[0] and buff[0].isprintable():
        return buff[0], result
    return None, result


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    WM_QUIT = 0x0012

    _LRESULT = ctypes.c_ssize_t
    _HHOOK = wintypes.HHOOK
    _HOOKPROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    _user32.SetWindowsHookExW.restype = _HHOOK
    _user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int,
        _HOOKPROC,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    ]
    _user32.CallNextHookEx.restype = _LRESULT
    _user32.CallNextHookEx.argtypes = [_HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    _user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    _user32.UnhookWindowsHookEx.argtypes = [_HHOOK]
    _user32.GetMessageW.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
    ]
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class _Win32KeyboardHook:
        def __init__(self, on_key_down: Callable[[int], bool]) -> None:
            self._on_key_down = on_key_down
            self._hook_id = _HHOOK(0)
            self._thread: threading.Thread | None = None
            self._thread_id: int | None = None
            self._proc = _HOOKPROC(self._handler)

        def _handler(self, n_code: int, w_param: int, l_param: int) -> int:
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kb = ctypes.cast(l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                try:
                    if self._on_key_down(int(kb.vkCode)):
                        return 1
                except Exception as exc:
                    log_warning(f"hook handler error vk={kb.vkCode}: {exc}")
            hook = self._hook_id or _HHOOK(0)
            return _user32.CallNextHookEx(hook, n_code, w_param, l_param)

        def start(self) -> bool:
            if self._thread is not None:
                return True

            def run() -> None:
                self._thread_id = _kernel32.GetCurrentThreadId()
                self._hook_id = _user32.SetWindowsHookExW(
                    WH_KEYBOARD_LL, self._proc, None, 0
                )
                if not self._hook_id:
                    log_warning(
                        f"SetWindowsHookExW failed: {_kernel32.GetLastError()}"
                    )
                    return
                log_info("hook thread running (Win32 WH_KEYBOARD_LL)")
                msg = wintypes.MSG()
                while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    _user32.TranslateMessage(ctypes.byref(msg))
                    _user32.DispatchMessageW(ctypes.byref(msg))
                if self._hook_id:
                    _user32.UnhookWindowsHookEx(self._hook_id)
                    self._hook_id = _HHOOK(0)

            self._thread = threading.Thread(
                target=run, name="QuickLingoKeyboardHook", daemon=True
            )
            self._thread.start()
            return True

        def stop(self) -> None:
            thread_id = self._thread_id
            thread = self._thread
            self._thread_id = None
            self._thread = None
            self._hook_id = _HHOOK(0)
            if thread_id is not None:
                _user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            if thread is not None:
                thread.join(timeout=0.05)

else:

    class _Win32KeyboardHook:
        def __init__(self, on_key_down: Callable[[int], bool]) -> None:
            self._on_key_down = on_key_down

        def start(self) -> bool:
            return False

        def stop(self) -> None:
            return


class TutorCaptureManager(QObject):
    character_typed = Signal(str)
    backspace_pressed = Signal()
    enter_pressed = Signal()

    def __init__(
        self,
        should_capture: Callable[[], bool] | None = None,
        should_capture_reason: Callable[[], str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._should_capture = should_capture or (lambda: True)
        self._should_capture_reason = should_capture_reason or (lambda: "ok")
        self._hook: _Win32KeyboardHook | None = None

    def start(self) -> None:
        if self.is_running():
            log_debug("start skipped: hook already running")
            return
        if sys.platform != "win32":
            log_warning("start skipped: not Windows")
            return

        log_info(f"hook starting; log file: {log_file_path()}")
        self._hook = _Win32KeyboardHook(self._on_key_down)
        if self._hook.start():
            log_info("hook started (Win32 WH_KEYBOARD_LL)")
        else:
            log_warning("hook failed to start")
            self._hook.stop()
            self._hook = None

    def stop(self) -> None:
        if self._hook is None:
            return
        log_info("hook stopping")
        self._hook.stop()
        self._hook = None
        log_info("hook stopped")

    def is_running(self) -> bool:
        return self._hook is not None

    def _on_key_down(self, vk: int) -> bool:
        key_label = f"vk={vk}"
        mods = _modifier_snapshot()
        layout = _keyboard_layout_id()

        if vk in _MODIFIER_VK_CODES:
            log_debug(f"PRESS {key_label} | modifier pass-through | {mods} | layout={layout}")
            return False

        if not self._should_capture():
            reason = self._should_capture_reason()
            log_debug(
                f"PRESS {key_label} | blocked should_capture reason={reason} | "
                f"{mods} | layout={layout}"
            )
            return False

        ctrl, alt, win = _modifiers_physical()
        if ctrl or alt or win:
            log_debug(
                f"PRESS {key_label} | blocked physical modifier "
                f"ctrl={ctrl} alt={alt} win={win} | {mods} | layout={layout}"
            )
            return False

        if vk == _VK_BACK:
            log_debug(f"PRESS {key_label} | CAPTURE backspace | {mods} | layout={layout}")
            self.backspace_pressed.emit()
            return True
        if vk == _VK_RETURN:
            log_debug(f"PRESS {key_label} | CAPTURE enter | {mods} | layout={layout}")
            self.enter_pressed.emit()
            return True

        char, unicode_result = _vk_to_typing_char(vk)
        if char is not None:
            log_debug(
                f"PRESS {key_label} | CAPTURE char={char!r} "
                f"unicode_result={unicode_result} | {mods} | layout={layout}"
            )
            self.character_typed.emit(char)
            return True

        log_debug(
            f"PRESS {key_label} | pass-through no char "
            f"unicode_result={unicode_result} | {mods} | layout={layout}"
        )
        return False
