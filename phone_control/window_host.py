"""Win32 window host for seamlessly docking borderless scrcpy windows into PhoneControl."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import threading
import time
from typing import Any


IS_WINDOWS = os.name == "nt"

GWL_STYLE = -16
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8

WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
WS_POPUP = 0x80000000

WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

SW_HIDE = 0
SW_SHOWNA = 8

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

# Win32 SendInput constants for sending Alt+O / Alt+Shift+O directly to scrcpy
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_LMENU = 0xA4
VK_LSHIFT = 0xA0
VK_O = 0x4F


if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8
    _LONG_PTR = ctypes.c_longlong if _IS_64 else ctypes.c_long
    _ULONG_PTR = ctypes.c_ulonglong if _IS_64 else ctypes.c_ulong

    if _IS_64:
        _get_window_long_ptr = _user32.GetWindowLongPtrW
        _set_window_long_ptr = _user32.SetWindowLongPtrW
    else:
        _get_window_long_ptr = _user32.GetWindowLongW
        _set_window_long_ptr = _user32.SetWindowLongW

    _get_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_window_long_ptr.restype = _LONG_PTR
    _set_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int, _LONG_PTR]
    _set_window_long_ptr.restype = _LONG_PTR

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]

    _user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    _user32.ClientToScreen.restype = wintypes.BOOL
    _user32.MoveWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.BOOL,
    ]
    _user32.MoveWindow.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindow.restype = wintypes.BOOL
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.FindWindowW.restype = wintypes.HWND
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.EnumWindows.argtypes = [_ENUM_PROC, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.GetForegroundWindow.argtypes = []
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int]
    _user32.SendInput.restype = ctypes.c_uint


def find_window_by_pid(pid: int, *, timeout: float = 5.0, title_contains: str = "") -> int | None:
    """Poll Win32 top-level windows until a visible window owned by `pid` appears."""
    if not IS_WINDOWS or pid <= 0:
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found: list[int] = []

        def _cb(hwnd: int, _lparam: int) -> bool:
            if not hwnd or not _user32.IsWindowVisible(hwnd):
                return True
            win_pid = wintypes.DWORD(0)
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
            if win_pid.value != pid:
                return True
            if title_contains:
                length = _user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                _user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_contains not in buf.value:
                    return True
            found.append(int(hwnd))
            return False

        _user32.EnumWindows(_ENUM_PROC(_cb), 0)
        if found:
            return found[0]
        time.sleep(0.08)
    return None


def find_window_by_title(title: str) -> int | None:
    if not IS_WINDOWS or not title:
        return None
    raw = _user32.FindWindowW(None, title)
    return int(raw) if raw else None


def _send_key_combo(vk_codes: list[int]) -> None:
    """Send a chord of virtual keys down then up via Win32 SendInput."""
    if not IS_WINDOWS:
        return
    events: list[_INPUT] = []
    for vk in vk_codes:
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)
        events.append(inp)
    for vk in reversed(vk_codes):
        inp = _INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)
        events.append(inp)
    arr = (_INPUT * len(events))(*events)
    _user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))


class Win32WindowHost:
    """Keeps borderless scrcpy windows docked inside the right workspace pane."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._owner_hwnd: int | None = None
        self._owner_title: str = ""
        self._children: dict[str, int] = {}  # serial -> hwnd
        self._slots: dict[str, dict[str, Any]] = {}
        self._overlay_visible: bool = True
        self._always_on_top: bool = False
        self._last_origin: tuple[int, int] | None = None
        self._last_iconic: bool | None = None
        self._stop_event = threading.Event()
        self._tracker_thread: threading.Thread | None = None

    def set_owner_title(self, title: str) -> None:
        with self._lock:
            self._owner_title = title
            self._resolve_owner_locked()

    def _resolve_owner_locked(self) -> int | None:
        if not IS_WINDOWS:
            return None
        if self._owner_hwnd and _user32.IsWindow(self._owner_hwnd):
            return self._owner_hwnd
        if self._owner_title:
            self._owner_hwnd = find_window_by_title(self._owner_title)
        return self._owner_hwnd

    def set_always_on_top(self, enabled: bool) -> bool:
        """Toggle HWND_TOPMOST on the main PhoneControl window (owned scrcpy windows follow)."""
        with self._lock:
            self._always_on_top = bool(enabled)
            if not IS_WINDOWS:
                return self._always_on_top
            owner = self._resolve_owner_locked()
            if owner:
                insert_after = HWND_TOPMOST if self._always_on_top else HWND_NOTOPMOST
                _user32.SetWindowPos(
                    owner,
                    insert_after,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
            return self._always_on_top

    def send_display_power_shortcut(self, serial: str, *, on: bool) -> bool:
        """Send native scrcpy Alt+O (off) or Alt+Shift+O (on) directly to the docked window."""
        if not IS_WINDOWS:
            return False
        with self._lock:
            hwnd = self._children.get(serial)
            if not hwnd or not _user32.IsWindow(hwnd):
                return False
            prev_fg = _user32.GetForegroundWindow()
            _user32.SetForegroundWindow(hwnd)
            time.sleep(0.04)
            combo = [VK_LMENU, VK_LSHIFT, VK_O] if on else [VK_LMENU, VK_O]
            _send_key_combo(combo)
            time.sleep(0.04)
            if prev_fg and _user32.IsWindow(prev_fg) and int(prev_fg) != int(hwnd):
                _user32.SetForegroundWindow(prev_fg)
            return True

    def start_tracking(self) -> None:
        if not IS_WINDOWS:
            return
        with self._lock:
            if self._tracker_thread and self._tracker_thread.is_alive():
                return
            self._stop_event.clear()
            self._tracker_thread = threading.Thread(
                target=self._track_loop,
                name="PhoneControl-WindowHost",
                daemon=True,
            )
            self._tracker_thread.start()

    def stop_tracking(self) -> None:
        self._stop_event.set()
        if self._tracker_thread and self._tracker_thread.is_alive():
            self._tracker_thread.join(timeout=0.5)

    def register_mirror(self, serial: str, pid: int, title_hint: str = "") -> bool:
        """Find the newly launched scrcpy HWND and dock it as an owned borderless window."""
        if not IS_WINDOWS:
            return False
        hwnd = find_window_by_pid(pid, timeout=6.0, title_contains=title_hint)
        if not hwnd:
            hwnd = find_window_by_pid(pid, timeout=1.5)
        if not hwnd:
            return False

        with self._lock:
            owner = self._resolve_owner_locked()
            self._children[serial] = hwnd
            if owner:
                self._apply_owned_style(hwnd, owner)
            self._reposition_serial_locked(serial)
        self.start_tracking()
        return True

    def unregister_mirror(self, serial: str) -> None:
        with self._lock:
            self._children.pop(serial, None)
            self._slots.pop(serial, None)

    def has_window(self, serial: str) -> bool:
        with self._lock:
            hwnd = self._children.get(serial)
            return bool(hwnd and IS_WINDOWS and _user32.IsWindow(hwnd))

    def set_overlay_visible(self, visible: bool) -> None:
        with self._lock:
            self._overlay_visible = bool(visible)
            self._reposition_all_locked(force=True)

    def sync_slots(self, slots: list[dict[str, Any]]) -> dict[str, Any]:
        """Update relative client coordinates (physical px) for active mirror slots."""
        with self._lock:
            self._resolve_owner_locked()
            if self._always_on_top and self._owner_hwnd:
                _user32.SetWindowPos(
                    self._owner_hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
                )
            active_serials: set[str] = set()
            for item in slots:
                serial = str(item.get("serial", ""))
                if not serial:
                    continue
                active_serials.add(serial)
                self._slots[serial] = {
                    "x": int(round(float(item.get("x", 0)))),
                    "y": int(round(float(item.get("y", 0)))),
                    "width": max(1, int(round(float(item.get("width", 1))))),
                    "height": max(1, int(round(float(item.get("height", 1))))),
                    "visible": bool(item.get("visible", True)),
                }

            for serial in list(self._children.keys()):
                if serial not in active_serials:
                    self._slots[serial] = {"x": 0, "y": 0, "width": 1, "height": 1, "visible": False}

            self._reposition_all_locked(force=True)
            return {"synced": len(active_serials), "attached": len(self._children)}

    def get_client_origin(self) -> tuple[int, int] | None:
        if not IS_WINDOWS:
            return None
        with self._lock:
            owner = self._resolve_owner_locked()
            if not owner:
                return None
            pt = wintypes.POINT(0, 0)
            if not _user32.ClientToScreen(owner, ctypes.byref(pt)):
                return None
            return (int(pt.x), int(pt.y))

    def _apply_owned_style(self, child_hwnd: int, owner_hwnd: int) -> None:
        if not IS_WINDOWS:
            return
        try:
            _set_window_long_ptr(child_hwnd, GWLP_HWNDPARENT, owner_hwnd)

            style = int(_get_window_long_ptr(child_hwnd, GWL_STYLE))
            style = (style & ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)) | WS_POPUP
            _set_window_long_ptr(child_hwnd, GWL_STYLE, style)

            ex_style = int(_get_window_long_ptr(child_hwnd, GWL_EXSTYLE))
            ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            _set_window_long_ptr(child_hwnd, GWL_EXSTYLE, ex_style)

            _user32.SetWindowPos(
                child_hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    def _reposition_serial_locked(self, serial: str) -> None:
        if not IS_WINDOWS:
            return
        hwnd = self._children.get(serial)
        if not hwnd:
            return
        if not _user32.IsWindow(hwnd):
            self._children.pop(serial, None)
            return

        owner = self._resolve_owner_locked()
        if not owner:
            return

        owner_iconic = bool(_user32.IsIconic(owner)) or not bool(_user32.IsWindowVisible(owner))
        slot = self._slots.get(serial)
        if owner_iconic or not self._overlay_visible or not slot or not slot.get("visible", True):
            _user32.ShowWindow(hwnd, SW_HIDE)
            return

        pt = wintypes.POINT(0, 0)
        if not _user32.ClientToScreen(owner, ctypes.byref(pt)):
            return

        screen_x = int(pt.x) + slot["x"]
        screen_y = int(pt.y) + slot["y"]
        w = slot["width"]
        h = slot["height"]
        if w < 40 or h < 40:
            _user32.ShowWindow(hwnd, SW_HIDE)
            return

        _user32.ShowWindow(hwnd, SW_SHOWNA)
        _user32.MoveWindow(hwnd, screen_x, screen_y, w, h, True)

    def _reposition_all_locked(self, *, force: bool = False) -> None:
        if not IS_WINDOWS:
            return
        owner = self._resolve_owner_locked()
        if not owner:
            return
        iconic = bool(_user32.IsIconic(owner)) or not bool(_user32.IsWindowVisible(owner))
        pt = wintypes.POINT(0, 0)
        origin = (int(pt.x), int(pt.y)) if _user32.ClientToScreen(owner, ctypes.byref(pt)) else None

        if not force and origin == self._last_origin and iconic == self._last_iconic:
            return
        self._last_origin = origin
        self._last_iconic = iconic

        for serial in list(self._children.keys()):
            self._reposition_serial_locked(serial)

    def _track_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    if self._children:
                        self._reposition_all_locked(force=False)
            except Exception:
                pass
            self._stop_event.wait(0.035)
