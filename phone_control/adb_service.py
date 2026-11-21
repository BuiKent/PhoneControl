"""ADB & scrcpy service layer for discovering, mirroring, and controlling Android devices."""

from __future__ import annotations

import ctypes
import io
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

QUALITY_PROFILES: dict[str, dict[str, str]] = {
    "balanced": {"bit_rate": "8M", "max_fps": "60", "max_size": "0"},
    "high": {"bit_rate": "16M", "max_fps": "60", "max_size": "0"},
    "lite": {"bit_rate": "4M", "max_fps": "30", "max_size": "1280"},
}

SWIPE_STEP_RATIOS: dict[str, tuple[float, int]] = {
    "short": (0.22, 220),
    "medium": (0.44, 280),
    "long": (0.68, 340),
}

KEYEVENT_ACTIONS: dict[str, list[str]] = {
    "back": ["shell", "input", "keyevent", "4"],
    "home": ["shell", "input", "keyevent", "3"],
    "recents": ["shell", "input", "keyevent", "187"],
    "select": ["shell", "input", "keyevent", "66"],
    "vol_up": ["shell", "input", "keyevent", "24"],
    "vol_down": ["shell", "input", "keyevent", "25"],
    "mute": ["shell", "input", "keyevent", "164"],
    "power": ["shell", "input", "keyevent", "26"],
    "wake": ["shell", "input", "keyevent", "224"],
    "notifications": ["shell", "cmd", "statusbar", "expand-notifications"],
    "quick_settings": ["shell", "cmd", "statusbar", "expand-settings"],
}

QUICK_APP_INTENTS: dict[str, list[list[str]]] = {
    "phone": [
        ["shell", "am", "start", "-a", "android.intent.action.DIAL"],
    ],
    "camera": [
        ["shell", "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA"],
        ["shell", "input", "keyevent", "27"],
    ],
    "messages": [
        ["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.APP_MESSAGING"],
        ["shell", "monkey", "-p", "com.samsung.android.messaging", "-c", "android.intent.category.LAUNCHER", "1"],
        ["shell", "monkey", "-p", "com.google.android.apps.messaging", "-c", "android.intent.category.LAUNCHER", "1"],
    ],
    "gallery": [
        ["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.APP_GALLERY"],
        ["shell", "monkey", "-p", "com.sec.android.gallery3d", "-c", "android.intent.category.LAUNCHER", "1"],
        ["shell", "monkey", "-p", "com.google.android.apps.photos", "-c", "android.intent.category.LAUNCHER", "1"],
    ],
}


@dataclass(frozen=True)
class ToolPaths:
    adb: Path | None
    scrcpy: Path | None


def discover_tools() -> ToolPaths:
    """Locate scrcpy.exe and adb.exe across WinGet packages, PATH, and local SDK folders."""
    scrcpy_path: Path | None = None
    adb_path: Path | None = None

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_root.exists():
            matches = sorted(
                winget_root.glob("Genymobile.scrcpy*/**/scrcpy.exe"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                scrcpy_path = matches[0]
                sibling_adb = scrcpy_path.parent / "adb.exe"
                if sibling_adb.exists():
                    adb_path = sibling_adb

    if not scrcpy_path:
        found = shutil.which("scrcpy")
        if found:
            scrcpy_path = Path(found)

    if not adb_path:
        for candidate in [
            shutil.which("adb"),
            str(scrcpy_path.parent / "adb.exe") if scrcpy_path else None,
            os.path.join(local_app_data, "Android", "Sdk", "platform-tools", "adb.exe") if local_app_data else None,
        ]:
            if candidate and Path(candidate).exists():
                adb_path = Path(candidate)
                break

    return ToolPaths(adb=adb_path, scrcpy=scrcpy_path)


def parse_adb_devices(output: str) -> list[dict[str, Any]]:
    """Parse `adb devices -l` output into structured device entries."""
    devices: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        attrs: dict[str, str] = {}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                attrs[key] = value

        is_wifi = ":" in serial and not serial.startswith("emulator-")
        devices.append(
            {
                "serial": serial,
                "state": state,
                "model": attrs.get("model", "").replace("_", " "),
                "product": attrs.get("product", ""),
                "device": attrs.get("device", ""),
                "transport_id": attrs.get("transport_id", ""),
                "transport": "wifi" if is_wifi else "usb",
            }
        )
    return devices


def parse_battery_level(dumpsys_output: str) -> int | None:
    match = re.search(r"^\s*level:\s*(\d+)\s*$", dumpsys_output, re.MULTILINE)
    if not match:
        return None
    val = int(match.group(1))
    return val if 0 <= val <= 100 else None


def parse_wifi_ip(ip_output: str) -> str:
    """Extract IPv4 address from `ip route` or `ip -f inet addr show wlan0` output."""
    for pattern in (
        r"\bsrc\s+(\d{1,3}(?:\.\d{1,3}){3})\b",
        r"\binet\s+(\d{1,3}(?:\.\d{1,3}){3})(?:/\d+)?\b",
    ):
        match = re.search(pattern, ip_output)
        if match:
            ip = match.group(1)
            if not ip.startswith("127."):
                return ip
    return ""


def parse_wm_size(output: str) -> tuple[int, int] | None:
    """Parse `adb shell wm size` output; prefer Override size over Physical size."""
    override = re.search(r"Override\s+size:\s*(\d+)x(\d+)", output)
    if override:
        w, h = int(override.group(1)), int(override.group(2))
        if w > 0 and h > 0:
            return (w, h)
    physical = re.search(r"Physical\s+size:\s*(\d+)x(\d+)", output)
    if physical:
        w, h = int(physical.group(1)), int(physical.group(2))
        if w > 0 and h > 0:
            return (w, h)
    return None


def parse_scrcpy_app_list(output: str) -> list[dict[str, Any]]:
    """Parse `scrcpy --list-apps` stdout into sorted `{name, package, system}` items."""
    apps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in output.splitlines():
        match = re.match(r"^\s*([*-])\s+(.+?)\s{2,}([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)\s*$", line)
        if not match:
            continue
        marker, name, pkg = match.group(1), match.group(2).strip(), match.group(3).strip()
        if pkg in seen:
            continue
        seen.add(pkg)
        apps.append({"name": name, "package": pkg, "system": marker == "*"})
    apps.sort(key=lambda item: item["name"].lower())
    return apps


def compute_swipe_coords(
    width: int,
    height: int,
    direction: str,
    step: str = "medium",
) -> tuple[int, int, int, int, int]:
    """Compute (x1, y1, x2, y2, duration_ms) for directional touch swipes."""
    ratio, duration = SWIPE_STEP_RATIOS.get(step, SWIPE_STEP_RATIOS["medium"])
    cx = width // 2
    cy = height // 2
    dy = max(60, int(height * ratio / 2))
    dx = max(60, int(width * ratio / 2))

    if direction == "up":
        # Finger moves upward -> scrolls page content down
        return (cx, min(height - 40, cy + dy), cx, max(40, cy - dy), duration)
    if direction == "down":
        # Finger moves downward -> scrolls page content up
        return (cx, max(40, cy - dy), cx, min(height - 40, cy + dy), duration)
    if direction == "left":
        # Finger moves left -> next page/tab
        return (min(width - 40, cx + dx), cy, max(40, cx - dx), cy, duration)
    if direction == "right":
        # Finger moves right -> previous page/tab
        return (max(40, cx - dx), cy, min(width - 40, cx + dx), cy, duration)
    raise ValueError(f"Hướng vuốt không hợp lệ: {direction}")


def build_scrcpy_args(
    scrcpy_path: Path,
    serial: str,
    *,
    title: str,
    settings: dict[str, Any],
    borderless: bool = False,
    initial_rect: dict[str, int] | None = None,
) -> list[str]:
    """Construct validated scrcpy CLI arguments."""
    quality_key = settings.get("quality", "balanced")
    profile = QUALITY_PROFILES.get(quality_key, QUALITY_PROFILES["balanced"])

    args = [
        str(scrcpy_path),
        "-s",
        serial,
        f"--video-bit-rate={profile['bit_rate']}",
        f"--max-fps={profile['max_fps']}",
        f"--window-title={title}",
    ]
    if profile["max_size"] != "0":
        args.append(f"--max-size={profile['max_size']}")
    if settings.get("stay_awake", True):
        args.append("--stay-awake")
    if settings.get("turn_screen_off", False):
        args.append("--turn-screen-off")
    if settings.get("always_on_top", False) and not borderless:
        args.append("--always-on-top")
    if not settings.get("enable_audio", True):
        args.append("--no-audio")
    if borderless:
        args.append("--window-borderless")
    if initial_rect:
        for flag, key in (
            ("--window-x", "x"),
            ("--window-y", "y"),
            ("--window-width", "width"),
            ("--window-height", "height"),
        ):
            if key in initial_rect and initial_rect[key] is not None:
                args.append(f"{flag}={int(initial_rect[key])}")
    return args


def copy_png_to_windows_clipboard(png_bytes: bytes) -> bool:
    """Copy a PNG image into Windows Clipboard as CF_DIB using PIL + Win32 API."""
    if os.name != "nt":
        return False
    try:
        from PIL import Image
    except ImportError:
        return False

    try:
        with Image.open(io.BytesIO(png_bytes)) as img:
            rgb = img.convert("RGB")
            bmp_buffer = io.BytesIO()
            rgb.save(bmp_buffer, "BMP")
            dib_data = bmp_buffer.getvalue()[14:]  # strip 14-byte BITMAPFILEHEADER
    except Exception:
        return False

    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    if not user32.OpenClipboard(None):
        return False
    hmem = None
    try:
        user32.EmptyClipboard()
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_data))
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            return False
        try:
            ctypes.memmove(ptr, dib_data, len(dib_data))
        finally:
            kernel32.GlobalUnlock(hmem)
        if not user32.SetClipboardData(CF_DIB, hmem):
            return False
        hmem = None  # ownership transferred to OS clipboard
        return True
    finally:
        if hmem:
            kernel32.GlobalFree(hmem)
        user32.CloseClipboard()


def sanitize_filename_part(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    return cleaned or "Android"


class AdbScrcpyService:
    """Manages ADB commands and active scrcpy mirroring processes."""

    def __init__(
        self,
        tools: ToolPaths | None = None,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
        clipboard_fn: Callable[[bytes], bool] = copy_png_to_windows_clipboard,
    ) -> None:
        self.tools = tools if tools is not None else discover_tools()
        self._run = runner
        self._popen = popen_factory
        self._clipboard = clipboard_fn
        self._mirror_procs: dict[str, subprocess.Popen] = {}
        self._detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._app_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def _require_adb(self) -> Path:
        if not self.tools.adb or not self.tools.adb.exists():
            raise RuntimeError("Không tìm thấy adb.exe. Hãy kiểm tra lại cài đặt scrcpy.")
        return self.tools.adb

    def _require_scrcpy(self) -> Path:
        if not self.tools.scrcpy or not self.tools.scrcpy.exists():
            raise RuntimeError("Không tìm thấy scrcpy.exe. Hãy cài đặt scrcpy trước.")
        return self.tools.scrcpy

    def run_adb(
        self,
        args: list[str],
        *,
        serial: str | None = None,
        timeout: float = 10.0,
        binary: bool = False,
    ) -> subprocess.CompletedProcess:
        adb = self._require_adb()
        cmd = [str(adb)]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)
        kwargs: dict[str, Any] = {
            "capture_output": True,
            "timeout": timeout,
            "creationflags": CREATE_NO_WINDOW,
        }
        if not binary:
            kwargs["text"] = True
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
        return self._run(cmd, **kwargs)

    def get_tool_status(self) -> dict[str, Any]:
        return {
            "adb_available": bool(self.tools.adb and self.tools.adb.exists()),
            "adb_path": str(self.tools.adb) if self.tools.adb else "",
            "scrcpy_available": bool(self.tools.scrcpy and self.tools.scrcpy.exists()),
            "scrcpy_path": str(self.tools.scrcpy) if self.tools.scrcpy else "",
        }

    def list_devices(self, *, fetch_details: bool = True) -> list[dict[str, Any]]:
        proc = self.run_adb(["devices", "-l"], timeout=8.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Lỗi chạy adb devices").strip())
        devices = parse_adb_devices(proc.stdout)
        self._prune_dead_mirrors()

        for dev in devices:
            serial = dev["serial"]
            dev["mirroring"] = serial in self._mirror_procs
            if fetch_details and dev["state"] == "device":
                details = self.get_device_details(serial)
                dev.update(details)
                dev["hardware_serial"] = details.get("hardware_serial") or serial
            else:
                dev.setdefault("manufacturer", "")
                dev.setdefault("android_version", "")
                dev.setdefault("battery", None)
                dev.setdefault("screen_width", 0)
                dev.setdefault("screen_height", 0)
                dev.setdefault("show_touches", False)
                dev.setdefault("wifi_ip", serial.split(":")[0] if dev["transport"] == "wifi" else "")
                dev["hardware_serial"] = serial
        return devices

    def get_device_details(self, serial: str, *, ttl_seconds: float = 12.0) -> dict[str, Any]:
        now = time.monotonic()
        cached = self._detail_cache.get(serial)
        if cached and (now - cached[0]) < ttl_seconds:
            return dict(cached[1])

        prop_cmd = (
            "echo MFR=$(getprop ro.product.manufacturer);"
            "echo MDL=$(getprop ro.product.model);"
            "echo VER=$(getprop ro.build.version.release);"
            "echo SER=$(getprop ro.serialno);"
            "echo TCH=$(settings get system show_touches 2>/dev/null);"
            "wm size 2>/dev/null;"
            "ip -f inet addr show wlan0 2>/dev/null || ip route 2>/dev/null"
        )
        prop_proc = self.run_adb(["shell", prop_cmd], serial=serial, timeout=5.0)
        info: dict[str, Any] = {
            "manufacturer": "",
            "model": "",
            "android_version": "",
            "hardware_serial": "",
            "wifi_ip": "",
            "battery": None,
            "screen_width": 1080,
            "screen_height": 2340,
            "show_touches": False,
        }
        if prop_proc.returncode == 0:
            out = prop_proc.stdout
            for line in out.splitlines():
                if line.startswith("MFR="):
                    info["manufacturer"] = line[4:].strip()
                elif line.startswith("MDL="):
                    info["model"] = line[4:].strip()
                elif line.startswith("VER="):
                    info["android_version"] = line[4:].strip()
                elif line.startswith("SER="):
                    info["hardware_serial"] = line[4:].strip()
                elif line.startswith("TCH="):
                    info["show_touches"] = line[4:].strip() == "1"
            info["wifi_ip"] = parse_wifi_ip(out)
            size = parse_wm_size(out)
            if size:
                info["screen_width"], info["screen_height"] = size

        bat_proc = self.run_adb(["shell", "dumpsys", "battery"], serial=serial, timeout=5.0)
        if bat_proc.returncode == 0:
            info["battery"] = parse_battery_level(bat_proc.stdout)

        self._detail_cache[serial] = (now, dict(info))
        return info

    def get_screen_size(self, serial: str) -> tuple[int, int]:
        details = self.get_device_details(serial)
        w = int(details.get("screen_width") or 1080)
        h = int(details.get("screen_height") or 2340)
        return (w, h)

    def _prune_dead_mirrors(self) -> None:
        dead = [s for s, p in self._mirror_procs.items() if p.poll() is not None]
        for serial in dead:
            del self._mirror_procs[serial]

    def is_mirroring(self, serial: str) -> bool:
        self._prune_dead_mirrors()
        return serial in self._mirror_procs

    def get_active_mirrors(self) -> list[str]:
        self._prune_dead_mirrors()
        return list(self._mirror_procs.keys())

    def start_mirror(
        self,
        serial: str,
        *,
        title: str,
        settings: dict[str, Any],
        borderless: bool = False,
        initial_rect: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        scrcpy = self._require_scrcpy()
        self._prune_dead_mirrors()
        if serial in self._mirror_procs:
            return {"serial": serial, "pid": self._mirror_procs[serial].pid, "already_running": True}

        args = build_scrcpy_args(
            scrcpy,
            serial,
            title=title,
            settings=settings,
            borderless=borderless,
            initial_rect=initial_rect,
        )
        proc = self._popen(
            args,
            cwd=str(scrcpy.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
        )
        time.sleep(0.35)
        if proc.poll() is not None:
            err = ""
            if proc.stderr:
                raw_err = proc.stderr.read()
                err = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
            raise RuntimeError(err.strip() or f"scrcpy thoát ngay với mã lỗi {proc.returncode}")

        self._mirror_procs[serial] = proc
        return {"serial": serial, "pid": proc.pid, "already_running": False}

    def stop_mirror(self, serial: str) -> bool:
        self._prune_dead_mirrors()
        proc = self._mirror_procs.pop(serial, None)
        if not proc:
            return False
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return True

    def stop_all_mirrors(self) -> None:
        for serial in list(self._mirror_procs.keys()):
            self.stop_mirror(serial)

    def set_display_power(self, serial: str, *, on: bool) -> dict[str, Any]:
        """Turn physical phone screen off (keeping mirror alive) or wake it back on."""
        if on:
            proc = self.run_adb(["shell", "input", "keyevent", "224"], serial=serial, timeout=6.0)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Không bật sáng màn hình được").strip())
            return {"serial": serial, "screen_on": True}

        # Use a short-lived headless scrcpy helper (same technique as escrcpy) so
        # physical display turns off anytime without disrupting an active mirror.
        scrcpy = self._require_scrcpy()
        cmd = [
            str(scrcpy),
            "-s",
            serial,
            "--no-window",
            "--no-video",
            "--no-audio",
            "--turn-screen-off",
        ]
        proc = self._popen(
            cmd,
            cwd=str(scrcpy.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
        )
        # Allow scrcpy server ~1.1s to connect and issue SET_DISPLAY_POWER_MODE(OFF),
        # then cleanly terminate the helper so it never lingers.
        time.sleep(1.1)
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        elif proc.returncode != 0:
            err = ""
            if proc.stderr:
                raw_err = proc.stderr.read()
                err = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
            raise RuntimeError(err.strip() or "Không tắt được màn hình vật lý.")
        return {"serial": serial, "screen_on": False}

    def set_show_touches(self, serial: str, enabled: bool) -> dict[str, Any]:
        val = "1" if enabled else "0"
        proc = self.run_adb(["shell", "settings", "put", "system", "show_touches", val], serial=serial, timeout=5.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không đổi được chấm chạm trắng").strip())
        cached = self._detail_cache.get(serial)
        if cached:
            cached[1]["show_touches"] = bool(enabled)
        return {"serial": serial, "show_touches": bool(enabled)}

    def swipe(self, serial: str, direction: str, *, step: str = "medium") -> dict[str, Any]:
        w, h = self.get_screen_size(serial)
        x1, y1, x2, y2, dur = compute_swipe_coords(w, h, direction, step)
        proc = self.run_adb(
            ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur)],
            serial=serial,
            timeout=6.0,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không gửi được lệnh vuốt").strip())
        return {"serial": serial, "direction": direction, "step": step}

    def tap_center(self, serial: str) -> dict[str, Any]:
        w, h = self.get_screen_size(serial)
        cx, cy = w // 2, h // 2
        proc = self.run_adb(["shell", "input", "tap", str(cx), str(cy)], serial=serial, timeout=6.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không gửi được lệnh chạm").strip())
        return {"serial": serial, "x": cx, "y": cy}

    def open_app_drawer(self, serial: str) -> dict[str, Any]:
        """Open the All Apps drawer reliably across Samsung One UI & stock Android launchers."""
        w, h = self.get_screen_size(serial)
        cx = w // 2
        y_start = int(h * 0.78)
        y_end = int(h * 0.22)
        # Go to Home first so the swipe-up gesture always opens the Apps screen
        self.run_adb(["shell", "input", "keyevent", "3"], serial=serial, timeout=5.0)
        time.sleep(0.18)
        proc = self.run_adb(
            ["shell", "input", "swipe", str(cx), str(y_start), str(cx), str(y_end), "220"],
            serial=serial,
            timeout=6.0,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không mở được trang tất cả ứng dụng").strip())
        return {"serial": serial, "action": "app_drawer"}

    def launch_quick_app(self, serial: str, app_key: str) -> dict[str, Any]:
        commands = QUICK_APP_INTENTS.get(app_key)
        if not commands:
            raise ValueError(f"Ứng dụng nhanh không hợp lệ: {app_key}")

        last_err = ""
        for cmd in commands:
            proc = self.run_adb(cmd, serial=serial, timeout=6.0)
            combined = f"{proc.stdout} {proc.stderr}".strip()
            has_intent_error = "error:" in combined.lower() or "unable to resolve" in combined.lower() or "no activities found" in combined.lower()
            if proc.returncode == 0 and not has_intent_error:
                return {"serial": serial, "app_key": app_key}
            last_err = combined
        raise RuntimeError(last_err or f"Không mở được ứng dụng {app_key}.")

    def list_installed_apps(self, serial: str, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._app_cache.get(serial)
        if not force_refresh and cached and (now - cached[0]) < 120.0:
            return list(cached[1])

        scrcpy = self._require_scrcpy()
        proc = self._run(
            [str(scrcpy), "-s", serial, "--list-apps"],
            cwd=str(scrcpy.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20.0,
            creationflags=CREATE_NO_WINDOW,
        )
        apps = parse_scrcpy_app_list(f"{proc.stdout}\n{proc.stderr}")
        if not apps and proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không đọc được danh sách ứng dụng").strip())
        self._app_cache[serial] = (now, list(apps))
        return apps

    def launch_package(self, serial: str, package_name: str) -> dict[str, Any]:
        pkg = package_name.strip()
        if not re.match(r"^[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+$", pkg):
            raise ValueError(f"Tên gói ứng dụng không hợp lệ: {pkg}")
        proc = self.run_adb(
            ["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"],
            serial=serial,
            timeout=8.0,
        )
        combined = f"{proc.stdout} {proc.stderr}".strip()
        if proc.returncode != 0 or "no activities found" in combined.lower():
            raise RuntimeError(combined or f"Không mở được {pkg}")
        return {"serial": serial, "package": pkg}

    def send_action(self, serial: str, action: str) -> dict[str, Any]:
        if action == "rotate":
            return self._toggle_rotation(serial)
        if action == "app_drawer":
            return self.open_app_drawer(serial)
        if action == "tap_center":
            return self.tap_center(serial)
        if action not in KEYEVENT_ACTIONS:
            raise ValueError(f"Hành động không hợp lệ: {action}")
        proc = self.run_adb(KEYEVENT_ACTIONS[action], serial=serial, timeout=6.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không gửi được lệnh điều khiển").strip())
        return {"serial": serial, "action": action}

    def _toggle_rotation(self, serial: str) -> dict[str, Any]:
        cur = self.run_adb(
            ["shell", "settings", "get", "system", "user_rotation"],
            serial=serial,
            timeout=5.0,
        )
        raw_val = (cur.stdout or "0").strip()
        next_rot = "1" if raw_val in ("0", "2", "null", "") else "0"
        self.run_adb(
            ["shell", "settings", "put", "system", "accelerometer_rotation", "0"],
            serial=serial,
            timeout=5.0,
        )
        res = self.run_adb(
            ["shell", "settings", "put", "system", "user_rotation", next_rot],
            serial=serial,
            timeout=5.0,
        )
        if res.returncode != 0:
            raise RuntimeError((res.stderr or "Không xoay được màn hình").strip())
        return {"serial": serial, "action": "rotate", "rotation": int(next_rot)}

    def take_screenshot(
        self,
        serial: str,
        *,
        output_dir: Path,
        device_label: str = "Android",
        copy_clipboard: bool = True,
    ) -> dict[str, Any]:
        proc = self.run_adb(["exec-out", "screencap", "-p"], serial=serial, timeout=15.0, binary=True)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else str(proc.stderr)
            raise RuntimeError(err.strip() or "Chụp ảnh màn hình thất bại.")
        png_bytes = proc.stdout if isinstance(proc.stdout, bytes) else b""
        if not png_bytes.startswith(PNG_SIGNATURE):
            raise RuntimeError("Dữ liệu ảnh chụp không hợp lệ (màn hình có thể đang bị chặn bảo mật FLAG_SECURE).")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = sanitize_filename_part(device_label)
        target = output_dir / f"{safe_label}_{stamp}.png"
        counter = 1
        while target.exists():
            target = output_dir / f"{safe_label}_{stamp}_{counter}.png"
            counter += 1

        target.write_bytes(png_bytes)
        copied = self._clipboard(png_bytes) if copy_clipboard else False
        return {
            "path": str(target),
            "filename": target.name,
            "size_bytes": len(png_bytes),
            "copied_to_clipboard": copied,
        }

    def enable_wifi_adb(self, usb_serial: str, port: int = 5555) -> dict[str, Any]:
        details = self.get_device_details(usb_serial, ttl_seconds=0)
        wifi_ip = details.get("wifi_ip", "")
        if not wifi_ip:
            raise RuntimeError("Không lấy được địa chỉ IP Wi-Fi của điện thoại. Hãy bật Wi-Fi cùng mạng với máy tính.")

        tcp = self.run_adb(["tcpip", str(port)], serial=usb_serial, timeout=8.0)
        if tcp.returncode != 0:
            raise RuntimeError((tcp.stderr or tcp.stdout or "Không bật được chế độ Wi-Fi ADB").strip())

        time.sleep(1.2)
        target = f"{wifi_ip}:{port}"
        conn = self.run_adb(["connect", target], timeout=10.0)
        combined = f"{conn.stdout} {conn.stderr}".strip()
        if conn.returncode != 0 or ("connected" not in combined.lower() and "already" not in combined.lower()):
            raise RuntimeError(combined or f"Không kết nối được tới {target}")
        return {"wifi_ip": wifi_ip, "target": target, "message": combined}

    def connect_wifi(self, address: str) -> dict[str, Any]:
        addr = address.strip()
        if not addr:
            raise ValueError("Vui lòng nhập địa chỉ IP (vd: 192.168.1.15:5555).")
        if ":" not in addr:
            addr = f"{addr}:5555"
        res = self.run_adb(["connect", addr], timeout=10.0)
        combined = f"{res.stdout} {res.stderr}".strip()
        if res.returncode != 0 or ("connected" not in combined.lower() and "already" not in combined.lower()):
            raise RuntimeError(combined or f"Không thể kết nối tới {addr}")
        return {"target": addr, "message": combined}

    def pair_and_connect_wifi(self, pair_addr: str, pair_code: str, connect_addr: str = "") -> dict[str, Any]:
        p_addr = pair_addr.strip()
        p_code = pair_code.strip()
        if not p_addr or ":" not in p_addr:
            raise ValueError("Địa chỉ ghép nối phải có dạng IP:Cổng (vd: 192.168.1.15:37123).")
        if not p_code:
            raise ValueError("Vui lòng nhập mã ghép nối 6 chữ số.")

        pair_res = self.run_adb(["pair", p_addr, p_code], timeout=12.0)
        pair_msg = f"{pair_res.stdout} {pair_res.stderr}".strip()
        if pair_res.returncode != 0 or "successfully paired" not in pair_msg.lower():
            raise RuntimeError(pair_msg or "Ghép nối Wi-Fi thất bại.")

        result: dict[str, Any] = {"paired": True, "pair_message": pair_msg}
        c_addr = connect_addr.strip()
        if c_addr:
            conn = self.connect_wifi(c_addr)
            result["connected"] = True
            result["target"] = conn["target"]
            result["connect_message"] = conn["message"]
        return result

    def disconnect_wifi(self, address: str) -> dict[str, Any]:
        res = self.run_adb(["disconnect", address], timeout=8.0)
        return {"target": address, "message": f"{res.stdout} {res.stderr}".strip()}

    def send_file(self, serial: str, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp: {file_path}")
        if path.suffix.lower() == ".apk":
            res = self.run_adb(["install", "-r", str(path)], serial=serial, timeout=60.0)
            msg = f"{res.stdout} {res.stderr}".strip()
            if res.returncode != 0 or "success" not in msg.lower():
                raise RuntimeError(msg or "Cài đặt APK thất bại.")
            return {"mode": "apk", "filename": path.name, "message": f"Đã cài đặt {path.name}"}

        remote = f"/sdcard/Download/{path.name}"
        res = self.run_adb(["push", str(path), remote], serial=serial, timeout=60.0)
        msg = f"{res.stdout} {res.stderr}".strip()
        if res.returncode != 0:
            raise RuntimeError(msg or "Gửi tệp thất bại.")
        return {"mode": "push", "filename": path.name, "remote_path": remote, "message": f"Đã gửi tới Download/{path.name}"}
