"""ADB & scrcpy service layer for discovering, mirroring, controlling, and diagnosing Android devices."""

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

BATTERY_HEALTH_LABELS: dict[int, str] = {
    1: "Không rõ",
    2: "Tốt",
    3: "Quá nhiệt",
    4: "Hỏng / Chai nặng",
    5: "Quá áp",
    6: "Lỗi pin",
    7: "Quá lạnh",
}

BATTERY_STATUS_LABELS: dict[int, str] = {
    1: "Không rõ",
    2: "Đang sạc",
    3: "Đang xả",
    4: "Không sạc",
    5: "Đầy pin",
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


def parse_battery_info(dumpsys_output: str) -> dict[str, Any]:
    """Parse `dumpsys battery` into level, temperature_c, voltage_v, health, status, technology."""
    info: dict[str, Any] = {
        "level": None,
        "temperature_c": None,
        "voltage_v": None,
        "health_code": None,
        "health_label": "Không rõ",
        "status_code": None,
        "status_label": "Không rõ",
        "technology": "",
    }
    m_level = re.search(r"^\s*level:\s*(\d+)\s*$", dumpsys_output, re.MULTILINE)
    if m_level:
        val = int(m_level.group(1))
        if 0 <= val <= 100:
            info["level"] = val

    m_temp = re.search(r"^\s*temperature:\s*(-?\d+)\s*$", dumpsys_output, re.MULTILINE)
    if m_temp:
        info["temperature_c"] = round(int(m_temp.group(1)) / 10.0, 1)

    m_volt = re.search(r"^\s*voltage:\s*(\d+)\s*$", dumpsys_output, re.MULTILINE)
    if m_volt:
        raw_v = int(m_volt.group(1))
        info["voltage_v"] = round(raw_v / 1000.0, 2) if raw_v > 100 else round(float(raw_v), 2)

    m_health = re.search(r"^\s*health:\s*(\d+)\s*$", dumpsys_output, re.MULTILINE)
    if m_health:
        code = int(m_health.group(1))
        info["health_code"] = code
        info["health_label"] = BATTERY_HEALTH_LABELS.get(code, "Không rõ")

    m_status = re.search(r"^\s*status:\s*(\d+)\s*$", dumpsys_output, re.MULTILINE)
    if m_status:
        code = int(m_status.group(1))
        info["status_code"] = code
        info["status_label"] = BATTERY_STATUS_LABELS.get(code, "Không rõ")

    m_tech = re.search(r"^\s*technology:\s*(.+?)\s*$", dumpsys_output, re.MULTILINE)
    if m_tech:
        info["technology"] = m_tech.group(1).strip()

    return info


def parse_battery_level(dumpsys_output: str) -> int | None:
    return parse_battery_info(dumpsys_output)["level"]


def parse_wifi_ip(ip_output: str) -> str:
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


def parse_orientation(output: str) -> int:
    """Parse Android surface orientation (0=0°, 1=90° landscape, 2=180°, 3=270° landscape)."""
    for pattern in (
        r"SurfaceOrientation:\s*([0-3])",
        r"mCurrentOrientation=([0-3])",
        r"ORIENT=([0-3])",
    ):
        match = re.search(pattern, output)
        if match:
            return int(match.group(1))
    return 0


def oriented_dimensions(width: int, height: int, orientation: int) -> tuple[int, int]:
    """Return effective (display_width, display_height) accounting for portrait vs landscape."""
    short_side = min(width, height)
    long_side = max(width, height)
    if orientation in (1, 3):
        return (long_side, short_side)
    return (short_side, long_side)


def parse_meminfo(output: str) -> dict[str, Any]:
    total_kb = 0
    avail_kb = 0
    m_tot = re.search(r"MemTotal:\s*(\d+)\s*kB", output)
    m_avail = re.search(r"MemAvailable:\s*(\d+)\s*kB", output)
    if m_tot:
        total_kb = int(m_tot.group(1))
    if m_avail:
        avail_kb = int(m_avail.group(1))
    if total_kb <= 0:
        return {"total_gb": None, "used_gb": None, "available_gb": None, "used_pct": None}
    used_kb = max(0, total_kb - avail_kb)
    return {
        "total_gb": round(total_kb / (1024 * 1024), 1),
        "used_gb": round(used_kb / (1024 * 1024), 1),
        "available_gb": round(avail_kb / (1024 * 1024), 1),
        "used_pct": round((used_kb / total_kb) * 100),
    }


def parse_storage_df(output: str) -> dict[str, Any]:
    """Parse `df -k /data` line into GB metrics."""
    for line in reversed(output.splitlines()):
        parts = line.split()
        if len(parts) >= 5 and parts[1].isdigit() and parts[2].isdigit() and parts[3].isdigit():
            total_kb = int(parts[1])
            used_kb = int(parts[2])
            avail_kb = int(parts[3])
            pct = round((used_kb / total_kb) * 100) if total_kb > 0 else 0
            return {
                "total_gb": round(total_kb / (1024 * 1024), 1),
                "used_gb": round(used_kb / (1024 * 1024), 1),
                "free_gb": round(avail_kb / (1024 * 1024), 1),
                "used_pct": pct,
            }
    return {"total_gb": None, "used_gb": None, "free_gb": None, "used_pct": None}


def parse_wifi_signal(output: str) -> dict[str, Any]:
    ssid = ""
    rssi = None
    link_mbps = None
    m_ssid = re.search(r'SSID:\s*"?([^",\r\n]+)"?', output) or re.search(r'"([^"]+)"\s+[0-9a-f]{2}:[0-9a-f]{2}', output, re.I)
    if m_ssid and m_ssid.group(1) != "<unknown ssid>":
        ssid = m_ssid.group(1).strip()
    m_rssi = re.search(r"rssi[=:]\s*(-?\d+)", output, re.I)
    if m_rssi:
        val = int(m_rssi.group(1))
        if -127 <= val <= 0:
            rssi = val
    m_link = re.search(r"link[=:\s]+(\d+)", output, re.I)
    if m_link:
        link_mbps = int(m_link.group(1))

    quality = "Không rõ"
    if isinstance(rssi, int):
        if rssi >= -55:
            quality = "Rất mạnh"
        elif rssi >= -67:
            quality = "Tốt"
        elif rssi >= -75:
            quality = "Trung bình"
        else:
            quality = "Yếu"
    return {"ssid": ssid, "rssi_dbm": rssi, "link_mbps": link_mbps, "quality": quality}


def parse_recent_crashes(dropbox_output: str) -> list[dict[str, Any]]:
    """Parse `dumpsys dropbox` crash/ANR entries into structured list (newest first)."""
    entries: list[dict[str, Any]] = []
    for line in dropbox_output.splitlines():
        m = re.match(
            r"^\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(data_app_crash|data_app_anr|system_app_crash|system_app_anr)\b(.*)$",
            line,
        )
        if not m:
            continue
        ts, kind, rest = m.group(1), m.group(2), m.group(3)
        pkg_match = re.search(r"([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)", rest)
        entries.append(
            {
                "timestamp": ts,
                "type": "ANR (Treo)" if "anr" in kind else "Crash (Văng)",
                "raw_type": kind,
                "package": pkg_match.group(1) if pkg_match else "",
                "summary": rest.strip()[:100],
            }
        )
    entries.reverse()
    return entries[:12]


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
    ratio, duration = SWIPE_STEP_RATIOS.get(step, SWIPE_STEP_RATIOS["medium"])
    cx = width // 2
    cy = height // 2
    dy = max(60, int(height * ratio / 2))
    dx = max(60, int(width * ratio / 2))

    if direction == "up":
        return (cx, min(height - 40, cy + dy), cx, max(40, cy - dy), duration)
    if direction == "down":
        return (cx, max(40, cy - dy), cx, min(height - 40, cy + dy), duration)
    if direction == "left":
        return (min(width - 40, cx + dx), cy, max(40, cx - dx), cy, duration)
    if direction == "right":
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
            dib_data = bmp_buffer.getvalue()[14:]
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
        hmem = None
        return True
    finally:
        if hmem:
            kernel32.GlobalFree(hmem)
        user32.CloseClipboard()


def sanitize_filename_part(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
    return cleaned or "Android"


class AdbScrcpyService:
    """Manages ADB commands, active scrcpy mirrors, orientation tracking, and diagnostics."""

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
        self._screen_off_state: dict[str, bool] = {}

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

    def get_current_orientation(self, serial: str) -> int:
        proc = self.run_adb(
            ["shell", "dumpsys input | grep -m 1 SurfaceOrientation || dumpsys display | grep -m 1 mCurrentOrientation"],
            serial=serial,
            timeout=3.0,
        )
        if proc.returncode == 0:
            return parse_orientation(proc.stdout)
        return 0

    def list_devices(self, *, fetch_details: bool = True) -> list[dict[str, Any]]:
        proc = self.run_adb(["devices", "-l"], timeout=8.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Lỗi chạy adb devices").strip())
        devices = parse_adb_devices(proc.stdout)
        self._prune_dead_mirrors()

        for dev in devices:
            serial = dev["serial"]
            dev["mirroring"] = serial in self._mirror_procs
            dev["screen_off"] = bool(self._screen_off_state.get(serial, False))
            if fetch_details and dev["state"] == "device":
                details = self.get_device_details(serial)
                # Always poll orientation quickly when mirroring so frame rotates automatically!
                if dev["mirroring"]:
                    orient = self.get_current_orientation(serial)
                    details["orientation"] = orient
                    eff_w, eff_h = oriented_dimensions(
                        int(details.get("raw_width") or details.get("screen_width") or 1080),
                        int(details.get("raw_height") or details.get("screen_height") or 2340),
                        orient,
                    )
                    details["screen_width"] = eff_w
                    details["screen_height"] = eff_h
                dev.update(details)
                dev["hardware_serial"] = details.get("hardware_serial") or serial
            else:
                dev.setdefault("manufacturer", "")
                dev.setdefault("android_version", "")
                dev.setdefault("battery", None)
                dev.setdefault("screen_width", 0)
                dev.setdefault("screen_height", 0)
                dev.setdefault("orientation", 0)
                dev.setdefault("show_touches", False)
                dev.setdefault("pointer_location", False)
                dev.setdefault("wifi_ip", serial.split(":")[0] if dev["transport"] == "wifi" else "")
                dev["hardware_serial"] = serial
        return devices

    def get_device_details(self, serial: str, *, ttl_seconds: float = 10.0) -> dict[str, Any]:
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
            "echo PTR=$(settings get system pointer_location 2>/dev/null);"
            "wm size 2>/dev/null;"
            "dumpsys input | grep -m 1 SurfaceOrientation 2>/dev/null;"
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
            "raw_width": 1080,
            "raw_height": 2340,
            "screen_width": 1080,
            "screen_height": 2340,
            "orientation": 0,
            "show_touches": False,
            "pointer_location": False,
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
                elif line.startswith("PTR="):
                    info["pointer_location"] = line[4:].strip() == "1"
            info["wifi_ip"] = parse_wifi_ip(out)
            size = parse_wm_size(out)
            if size:
                info["raw_width"], info["raw_height"] = size
            orient = parse_orientation(out)
            info["orientation"] = orient
            info["screen_width"], info["screen_height"] = oriented_dimensions(
                info["raw_width"], info["raw_height"], orient
            )

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
            self._screen_off_state.pop(serial, None)

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
        self._screen_off_state[serial] = bool(settings.get("turn_screen_off", False))
        return {"serial": serial, "pid": proc.pid, "already_running": False}

    def stop_mirror(self, serial: str) -> bool:
        self._prune_dead_mirrors()
        proc = self._mirror_procs.pop(serial, None)
        self._screen_off_state.pop(serial, None)
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

    def mark_screen_off_state(self, serial: str, screen_off: bool) -> None:
        self._screen_off_state[serial] = bool(screen_off)

    def set_display_power(self, serial: str, *, on: bool) -> dict[str, Any]:
        """Turn physical phone screen off (keeping mirror alive) or reliably restore backlight."""
        if on:
            # When panel was powered off via SurfaceControl.setDisplayPowerMode(OFF),
            # plain KEYCODE_WAKEUP is ignored because Android already considers itself awake.
            # Cycling POWER -> short pause -> WAKEUP reliably restores the physical backlight.
            self.run_adb(["shell", "input", "keyevent", "26"], serial=serial, timeout=5.0)
            time.sleep(0.22)
            proc = self.run_adb(["shell", "input", "keyevent", "224"], serial=serial, timeout=6.0)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Không bật sáng màn hình được").strip())
            self._screen_off_state[serial] = False
            return {"serial": serial, "screen_on": True, "screen_off": False}

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
        self._screen_off_state[serial] = True
        return {"serial": serial, "screen_on": False, "screen_off": True}

    def set_show_touches(self, serial: str, enabled: bool) -> dict[str, Any]:
        val = "1" if enabled else "0"
        proc = self.run_adb(["shell", "settings", "put", "system", "show_touches", val], serial=serial, timeout=5.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không đổi được chấm chạm trắng").strip())
        cached = self._detail_cache.get(serial)
        if cached:
            cached[1]["show_touches"] = bool(enabled)
        return {"serial": serial, "show_touches": bool(enabled)}

    def set_pointer_location(self, serial: str, enabled: bool) -> dict[str, Any]:
        """Toggle Android touch grid & trace overlay to diagnose dead zones / ghost touches."""
        val = "1" if enabled else "0"
        proc = self.run_adb(["shell", "settings", "put", "system", "pointer_location", val], serial=serial, timeout=5.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không bật/tắt được chế độ kiểm tra cảm ứng").strip())
        cached = self._detail_cache.get(serial)
        if cached:
            cached[1]["pointer_location"] = bool(enabled)
        return {"serial": serial, "pointer_location": bool(enabled)}

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
        w, h = self.get_screen_size(serial)
        cx = w // 2
        y_start = int(h * 0.78)
        y_end = int(h * 0.22)
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
            has_intent_error = (
                "error:" in combined.lower()
                or "unable to resolve" in combined.lower()
                or "no activities found" in combined.lower()
            )
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

    def force_stop_package(self, serial: str, package_name: str) -> dict[str, Any]:
        pkg = package_name.strip()
        if not re.match(r"^[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+$", pkg):
            raise ValueError(f"Tên gói ứng dụng không hợp lệ: {pkg}")
        proc = self.run_adb(["shell", "am", "force-stop", pkg], serial=serial, timeout=6.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or f"Không buộc dừng được {pkg}").strip())
        return {"serial": serial, "package": pkg, "stopped": True}

    def get_diagnostics(self, serial: str) -> dict[str, Any]:
        """Collect battery health, RAM/storage, Wi-Fi signal, ping latency, and recent app crashes/ANRs."""
        bat_proc = self.run_adb(["shell", "dumpsys", "battery"], serial=serial, timeout=5.0)
        battery = parse_battery_info(bat_proc.stdout if bat_proc.returncode == 0 else "")

        sys_proc = self.run_adb(
            [
                "shell",
                "head -n 4 /proc/meminfo; echo '---DF---'; df -k /data | tail -n 1; "
                "echo '---POWERSAVE---'; settings get global low_power 2>/dev/null; "
                "echo '---PTR---'; settings get system pointer_location 2>/dev/null; "
                "echo '---HWTEST---'; pm list packages com.sec.android.app.hwmoduletest 2>/dev/null",
            ],
            serial=serial,
            timeout=6.0,
        )
        sys_out = sys_proc.stdout if sys_proc.returncode == 0 else ""
        mem = parse_meminfo(sys_out)
        df_section = sys_out.split("---DF---")[1].split("---POWERSAVE---")[0] if "---DF---" in sys_out else ""
        storage = parse_storage_df(df_section)
        power_save = "---POWERSAVE---\n1" in sys_out.replace("\r\n", "\n")
        pointer_loc = "---PTR---\n1" in sys_out.replace("\r\n", "\n")
        has_samsung_hwtest = "com.sec.android.app.hwmoduletest" in sys_out

        wifi_proc = self.run_adb(
            ["shell", "dumpsys wifi | grep -E 'mWifiInfo|CMD_ONESHOT_RSSI_POLL' | tail -n 3"],
            serial=serial,
            timeout=5.0,
        )
        wifi = parse_wifi_signal(wifi_proc.stdout if wifi_proc.returncode == 0 else "")

        ping_ms = None
        ping_proc = self.run_adb(["shell", "ping -c 1 -W 2 8.8.8.8 2>/dev/null"], serial=serial, timeout=5.0)
        if ping_proc.returncode == 0:
            m_ping = re.search(r"time=([0-9.]+)\s*ms", ping_proc.stdout)
            if m_ping:
                ping_ms = round(float(m_ping.group(1)), 1)

        crash_proc = self.run_adb(
            ["shell", "dumpsys dropbox | grep -E 'data_app_crash|data_app_anr|system_app_crash|system_app_anr' | tail -n 20"],
            serial=serial,
            timeout=6.0,
        )
        crashes = parse_recent_crashes(crash_proc.stdout if crash_proc.returncode == 0 else "")

        return {
            "serial": serial,
            "battery": battery,
            "memory": mem,
            "storage": storage,
            "wifi": wifi,
            "ping_ms": ping_ms,
            "power_save": power_save,
            "pointer_location": pointer_loc,
            "has_samsung_hwtest": has_samsung_hwtest,
            "crashes": crashes,
        }

    def set_battery_saver(self, serial: str, enabled: bool) -> dict[str, Any]:
        val = "1" if enabled else "0"
        proc = self.run_adb(["shell", "settings", "put", "global", "low_power", val], serial=serial, timeout=5.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không đổi được chế độ tiết kiệm pin").strip())
        return {"serial": serial, "power_save": bool(enabled)}

    def clear_background_processes(self, serial: str) -> dict[str, Any]:
        proc = self.run_adb(["shell", "am", "kill-all"], serial=serial, timeout=8.0)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Không dọn được tiến trình nền").strip())
        return {"serial": serial, "cleared": True}

    def launch_samsung_hw_test(self, serial: str) -> dict[str, Any]:
        """Launch Samsung built-in hardware diagnostics (*#0*# — RGB dead pixel, touch grid, sensors)."""
        for cmd in (
            ["shell", "am", "start", "-n", "com.sec.android.app.hwmoduletest/.HwModuleTest"],
            ["shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", "tel:*%230*%23"],
        ):
            proc = self.run_adb(cmd, serial=serial, timeout=6.0)
            combined = f"{proc.stdout} {proc.stderr}".strip()
            if proc.returncode == 0 and "error:" not in combined.lower():
                return {"serial": serial, "launched": True}
        raise RuntimeError("Không mở được trình kiểm tra phần cứng Samsung (có thể máy khóa Auto Blocker).")

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
        cur_orient = self.get_current_orientation(serial)
        next_rot = 0 if cur_orient in (1, 3) else 1
        self.run_adb(
            ["shell", "settings", "put", "system", "accelerometer_rotation", "0"],
            serial=serial,
            timeout=5.0,
        )
        res = self.run_adb(
            ["shell", "settings", "put", "system", "user_rotation", str(next_rot)],
            serial=serial,
            timeout=5.0,
        )
        if res.returncode != 0:
            raise RuntimeError((res.stderr or "Không xoay được màn hình").strip())

        details = self.get_device_details(serial)
        raw_w = int(details.get("raw_width") or details.get("screen_width") or 1080)
        raw_h = int(details.get("raw_height") or details.get("screen_height") or 2340)
        eff_w, eff_h = oriented_dimensions(raw_w, raw_h, next_rot)
        cached = self._detail_cache.get(serial)
        if cached:
            cached[1]["orientation"] = next_rot
            cached[1]["screen_width"] = eff_w
            cached[1]["screen_height"] = eff_h
        return {
            "serial": serial,
            "action": "rotate",
            "rotation": next_rot,
            "orientation": next_rot,
            "screen_width": eff_w,
            "screen_height": eff_h,
        }

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
