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

KEYEVENT_ACTIONS: dict[str, list[str]] = {
    "back": ["shell", "input", "keyevent", "4"],
    "home": ["shell", "input", "keyevent", "3"],
    "recents": ["shell", "input", "keyevent", "187"],
    "vol_up": ["shell", "input", "keyevent", "24"],
    "vol_down": ["shell", "input", "keyevent", "25"],
    "mute": ["shell", "input", "keyevent", "164"],
    "power": ["shell", "input", "keyevent", "26"],
    "wake": ["shell", "input", "keyevent", "224"],
    "notifications": ["shell", "cmd", "statusbar", "expand-notifications"],
    "quick_settings": ["shell", "cmd", "statusbar", "expand-settings"],
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


def build_scrcpy_args(
    scrcpy_path: Path,
    serial: str,
    *,
    title: str,
    settings: dict[str, Any],
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
    if settings.get("always_on_top", False):
        args.append("--always-on-top")
    if not settings.get("enable_audio", True):
        args.append("--no-audio")
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
            info["wifi_ip"] = parse_wifi_ip(out)

        bat_proc = self.run_adb(["shell", "dumpsys", "battery"], serial=serial, timeout=5.0)
        if bat_proc.returncode == 0:
            info["battery"] = parse_battery_level(bat_proc.stdout)

        self._detail_cache[serial] = (now, dict(info))
        return info

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

    def start_mirror(self, serial: str, *, title: str, settings: dict[str, Any]) -> dict[str, Any]:
        scrcpy = self._require_scrcpy()
        self._prune_dead_mirrors()
        if serial in self._mirror_procs:
            return {"serial": serial, "pid": self._mirror_procs[serial].pid, "already_running": True}

        args = build_scrcpy_args(scrcpy, serial, title=title, settings=settings)
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

    def send_action(self, serial: str, action: str) -> dict[str, Any]:
        if action == "rotate":
            return self._toggle_rotation(serial)
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
