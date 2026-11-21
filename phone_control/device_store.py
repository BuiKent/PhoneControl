"""Persistent storage for saved Android devices and user preferences."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_QUALITIES = ("balanced", "high", "lite")
VALID_SWIPE_STEPS = ("short", "medium", "long")
VALID_ZOOM_MODES = ("fit", "fill", "50", "75", "100", "125", "150")

DEFAULT_SETTINGS: dict[str, Any] = {
    "quality": "balanced",  # balanced (8M/60fps) | high (16M/60fps) | lite (4M/30fps)
    "turn_screen_off": False,
    "stay_awake": True,
    "always_on_top": False,
    "enable_audio": True,
    "auto_mirror_saved": False,
    "swipe_step": "medium",
    "zoom_mode": "fit",
    "sidebar_collapsed": False,
    "embedded_workspace": True,
    "screenshot_dir": "",
}


def default_screenshot_dir() -> Path:
    pictures = Path.home() / "Pictures"
    if not pictures.exists():
        pictures = Path.home()
    return pictures / "PhoneControl"


def default_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "PhoneControl" / "config.json"
    return Path.home() / ".phone_control" / "config.json"


class DeviceStore:
    """Thread-safe atomic JSON store for saved devices and scrcpy settings."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else default_config_path()
        self._data: dict[str, Any] = {
            "version": 2,
            "settings": deepcopy(DEFAULT_SETTINGS),
            "devices": {},
        }
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            self._ensure_screenshot_dir_default()
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._ensure_screenshot_dir_default()
            return

        if isinstance(raw, dict):
            merged_settings = deepcopy(DEFAULT_SETTINGS)
            if isinstance(raw.get("settings"), dict):
                for key in DEFAULT_SETTINGS:
                    if key in raw["settings"]:
                        merged_settings[key] = raw["settings"][key]
            if merged_settings["quality"] not in VALID_QUALITIES:
                merged_settings["quality"] = DEFAULT_SETTINGS["quality"]
            if merged_settings["swipe_step"] not in VALID_SWIPE_STEPS:
                merged_settings["swipe_step"] = DEFAULT_SETTINGS["swipe_step"]
            if str(merged_settings["zoom_mode"]) not in VALID_ZOOM_MODES:
                merged_settings["zoom_mode"] = DEFAULT_SETTINGS["zoom_mode"]
            else:
                merged_settings["zoom_mode"] = str(merged_settings["zoom_mode"])
            self._data["settings"] = merged_settings

            devices = raw.get("devices")
            self._data["devices"] = devices if isinstance(devices, dict) else {}
        self._ensure_screenshot_dir_default()

    def _ensure_screenshot_dir_default(self) -> None:
        if not self._data["settings"].get("screenshot_dir"):
            self._data["settings"]["screenshot_dir"] = str(default_screenshot_dir())

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.config_path.parent),
            prefix="config_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.config_path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def get_settings(self) -> dict[str, Any]:
        return deepcopy(self._data["settings"])

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        settings = self._data["settings"]
        for key, value in patch.items():
            if key not in DEFAULT_SETTINGS:
                continue
            if key == "quality" and value not in VALID_QUALITIES:
                continue
            if key == "swipe_step" and value not in VALID_SWIPE_STEPS:
                continue
            if key == "zoom_mode":
                val_str = str(value)
                if val_str not in VALID_ZOOM_MODES:
                    continue
                value = val_str
            settings[key] = value
        self._ensure_screenshot_dir_default()
        self.save()
        return self.get_settings()

    def get_saved_devices(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._data["devices"])

    def upsert_device(
        self,
        device_id: str,
        *,
        serial: str,
        model: str = "",
        manufacturer: str = "",
        android_version: str = "",
        wifi_ip: str = "",
        transport: str = "usb",
        screen_width: int = 0,
        screen_height: int = 0,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        existing = self._data["devices"].get(device_id, {})
        record = {
            "id": device_id,
            "serial": serial,
            "nickname": existing.get("nickname", ""),
            "model": model or existing.get("model", ""),
            "manufacturer": manufacturer or existing.get("manufacturer", ""),
            "android_version": android_version or existing.get("android_version", ""),
            "wifi_ip": wifi_ip or existing.get("wifi_ip", ""),
            "last_transport": transport or existing.get("last_transport", "usb"),
            "screen_width": screen_width or existing.get("screen_width", 0),
            "screen_height": screen_height or existing.get("screen_height", 0),
            "auto_mirror": bool(existing.get("auto_mirror", False)),
            "first_seen": existing.get("first_seen", now),
            "last_seen": now,
        }
        self._data["devices"][device_id] = record
        self.save()
        return deepcopy(record)

    def rename_device(self, device_id: str, nickname: str) -> dict[str, Any] | None:
        record = self._data["devices"].get(device_id)
        if not record:
            return None
        record["nickname"] = nickname.strip()[:60]
        self.save()
        return deepcopy(record)

    def set_device_auto_mirror(self, device_id: str, enabled: bool) -> dict[str, Any] | None:
        record = self._data["devices"].get(device_id)
        if not record:
            return None
        record["auto_mirror"] = bool(enabled)
        self.save()
        return deepcopy(record)

    def set_device_wifi_ip(self, device_id: str, wifi_ip: str) -> dict[str, Any] | None:
        record = self._data["devices"].get(device_id)
        if not record:
            return None
        record["wifi_ip"] = wifi_ip.strip()
        self.save()
        return deepcopy(record)

    def delete_device(self, device_id: str) -> bool:
        if device_id in self._data["devices"]:
            del self._data["devices"][device_id]
            self.save()
            return True
        return False
