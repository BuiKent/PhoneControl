"""Python-to-JS bridge API exposed to the pywebview frontend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adb_service import AdbScrcpyService
from .device_store import DeviceStore


def _ok(data: Any = None) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _err(exc: Exception | str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": str(exc)}


class PhoneControlAPI:
    """Exposed to window.pywebview.api for the desktop UI."""

    def __init__(
        self,
        service: AdbScrcpyService | None = None,
        store: DeviceStore | None = None,
    ) -> None:
        self.service = service or AdbScrcpyService()
        self.store = store or DeviceStore()
        self._window: Any = None
        self._seen_online_ids: set[str] = set()

    def attach_window(self, window: Any) -> None:
        self._window = window

    def get_initial_state(self) -> dict[str, Any]:
        try:
            devices_res = self.scan_devices(trigger_auto_mirror=False)
            return _ok(
                {
                    "tools": self.service.get_tool_status(),
                    "settings": self.store.get_settings(),
                    "devices": devices_res["data"]["devices"] if devices_res["ok"] else [],
                }
            )
        except Exception as exc:
            return _err(exc)

    def scan_devices(self, trigger_auto_mirror: bool = True) -> dict[str, Any]:
        """Combine live ADB devices with persisted device profiles and handle auto-mirror."""
        try:
            live_devices = self.service.list_devices(fetch_details=True)
            saved_map = self.store.get_saved_devices()
            settings = self.store.get_settings()

            merged: list[dict[str, Any]] = []
            seen_saved_ids: set[str] = set()
            current_online_ids: set[str] = set()
            auto_mirrored: list[str] = []

            for dev in live_devices:
                hw_id = dev.get("hardware_serial") or dev["serial"]
                seen_saved_ids.add(hw_id)
                saved = saved_map.get(hw_id)

                if dev["state"] == "device":
                    was_saved_before = saved is not None
                    saved = self.store.upsert_device(
                        hw_id,
                        serial=dev["serial"],
                        model=dev.get("model", ""),
                        manufacturer=dev.get("manufacturer", ""),
                        android_version=dev.get("android_version", ""),
                        wifi_ip=dev.get("wifi_ip", ""),
                        transport=dev.get("transport", "usb"),
                    )
                    current_online_ids.add(hw_id)

                    should_auto = (
                        trigger_auto_mirror
                        and was_saved_before
                        and hw_id not in self._seen_online_ids
                        and (settings.get("auto_mirror_saved") or saved.get("auto_mirror"))
                        and not dev.get("mirroring")
                    )
                    if should_auto:
                        try:
                            title = self._display_title(saved, dev)
                            self.service.start_mirror(dev["serial"], title=title, settings=settings)
                            dev["mirroring"] = True
                            auto_mirrored.append(dev["serial"])
                        except Exception:
                            pass

                display_name = self._display_title(saved, dev)
                merged.append(
                    {
                        "id": hw_id,
                        "serial": dev["serial"],
                        "state": dev["state"],
                        "online": dev["state"] == "device",
                        "transport": dev.get("transport", "usb"),
                        "display_name": display_name,
                        "nickname": saved.get("nickname", "") if saved else "",
                        "model": dev.get("model") or (saved.get("model", "") if saved else ""),
                        "manufacturer": dev.get("manufacturer") or (saved.get("manufacturer", "") if saved else ""),
                        "android_version": dev.get("android_version") or (saved.get("android_version", "") if saved else ""),
                        "battery": dev.get("battery"),
                        "wifi_ip": dev.get("wifi_ip") or (saved.get("wifi_ip", "") if saved else ""),
                        "mirroring": bool(dev.get("mirroring", False)),
                        "saved": saved is not None,
                        "auto_mirror": bool(saved.get("auto_mirror", False)) if saved else False,
                        "last_seen": saved.get("last_seen", "") if saved else "",
                    }
                )

            # Append saved-but-disconnected devices so users can reconnect via Wi-Fi or see history
            for hw_id, saved in saved_map.items():
                if hw_id in seen_saved_ids:
                    continue
                display_name = saved.get("nickname") or self._format_model_name(
                    saved.get("manufacturer", ""), saved.get("model", ""), saved.get("serial", hw_id)
                )
                merged.append(
                    {
                        "id": hw_id,
                        "serial": saved.get("serial", hw_id),
                        "state": "disconnected",
                        "online": False,
                        "transport": saved.get("last_transport", "usb"),
                        "display_name": display_name,
                        "nickname": saved.get("nickname", ""),
                        "model": saved.get("model", ""),
                        "manufacturer": saved.get("manufacturer", ""),
                        "android_version": saved.get("android_version", ""),
                        "battery": None,
                        "wifi_ip": saved.get("wifi_ip", ""),
                        "mirroring": False,
                        "saved": True,
                        "auto_mirror": bool(saved.get("auto_mirror", False)),
                        "last_seen": saved.get("last_seen", ""),
                    }
                )

            self._seen_online_ids = current_online_ids
            # Sort: online first, then unauthorized, then saved disconnected
            order = {"device": 0, "authorizing": 1, "unauthorized": 2, "offline": 3, "disconnected": 4}
            merged.sort(key=lambda d: (order.get(d["state"], 5), d["display_name"].lower()))
            return _ok({"devices": merged, "auto_mirrored": auto_mirrored})
        except Exception as exc:
            return _err(exc)

    @staticmethod
    def _format_model_name(manufacturer: str, model: str, fallback: str) -> str:
        mfr = manufacturer.strip()
        mdl = model.strip()
        if mfr and mdl:
            if mdl.lower().startswith(mfr.lower()):
                return mdl
            return f"{mfr.capitalize()} {mdl}"
        return mdl or fallback

    def _display_title(self, saved: dict[str, Any] | None, dev: dict[str, Any]) -> str:
        if saved and saved.get("nickname"):
            return saved["nickname"]
        mfr = dev.get("manufacturer") or (saved.get("manufacturer", "") if saved else "")
        mdl = dev.get("model") or (saved.get("model", "") if saved else "")
        return self._format_model_name(mfr, mdl, dev["serial"])

    def start_mirror(self, serial: str, display_name: str = "") -> dict[str, Any]:
        try:
            settings = self.store.get_settings()
            title = f"{display_name or serial} — Phone Control"
            res = self.service.start_mirror(serial, title=title, settings=settings)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def stop_mirror(self, serial: str) -> dict[str, Any]:
        try:
            stopped = self.service.stop_mirror(serial)
            return _ok({"serial": serial, "stopped": stopped})
        except Exception as exc:
            return _err(exc)

    def send_action(self, serial: str, action: str) -> dict[str, Any]:
        try:
            res = self.service.send_action(serial, action)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def take_screenshot(self, serial: str, device_label: str = "Android") -> dict[str, Any]:
        try:
            settings = self.store.get_settings()
            out_dir = Path(settings["screenshot_dir"])
            res = self.service.take_screenshot(
                serial,
                output_dir=out_dir,
                device_label=device_label or serial,
                copy_clipboard=True,
            )
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def open_screenshot_folder(self) -> dict[str, Any]:
        try:
            out_dir = Path(self.store.get_settings()["screenshot_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(str(out_dir))
            return _ok({"path": str(out_dir)})
        except Exception as exc:
            return _err(exc)

    def open_file(self, path: str) -> dict[str, Any]:
        try:
            p = Path(path)
            if not p.exists():
                return _err("Tệp không tồn tại.")
            if hasattr(os, "startfile"):
                os.startfile(str(p))
            return _ok({"path": str(p)})
        except Exception as exc:
            return _err(exc)

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        try:
            updated = self.store.update_settings(patch)
            return _ok(updated)
        except Exception as exc:
            return _err(exc)

    def rename_device(self, device_id: str, nickname: str) -> dict[str, Any]:
        try:
            updated = self.store.rename_device(device_id, nickname)
            if not updated:
                return _err("Không tìm thấy thiết bị đã lưu.")
            return _ok(updated)
        except Exception as exc:
            return _err(exc)

    def set_device_auto_mirror(self, device_id: str, enabled: bool) -> dict[str, Any]:
        try:
            updated = self.store.set_device_auto_mirror(device_id, enabled)
            if not updated:
                return _err("Không tìm thấy thiết bị đã lưu.")
            return _ok(updated)
        except Exception as exc:
            return _err(exc)

    def delete_saved_device(self, device_id: str) -> dict[str, Any]:
        try:
            deleted = self.store.delete_device(device_id)
            return _ok({"deleted": deleted})
        except Exception as exc:
            return _err(exc)

    def enable_wifi_for_device(self, usb_serial: str, device_id: str = "") -> dict[str, Any]:
        try:
            res = self.service.enable_wifi_adb(usb_serial)
            if device_id and res.get("wifi_ip"):
                self.store.set_device_wifi_ip(device_id, res["wifi_ip"])
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def connect_wifi(self, address: str) -> dict[str, Any]:
        try:
            res = self.service.connect_wifi(address)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def pair_and_connect_wifi(self, pair_addr: str, pair_code: str, connect_addr: str = "") -> dict[str, Any]:
        try:
            res = self.service.pair_and_connect_wifi(pair_addr, pair_code, connect_addr)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def disconnect_wifi(self, address: str) -> dict[str, Any]:
        try:
            res = self.service.disconnect_wifi(address)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def pick_and_send_file(self, serial: str) -> dict[str, Any]:
        try:
            if not self._window:
                return _err("Cửa sổ ứng dụng chưa sẵn sàng.")
            import webview

            selected = self._window.create_file_dialog(webview.FileDialog.OPEN)
            if not selected:
                return _ok({"cancelled": True})
            file_path = selected[0] if isinstance(selected, (list, tuple)) else str(selected)
            res = self.service.send_file(serial, file_path)
            return _ok(res)
        except Exception as exc:
            return _err(exc)
