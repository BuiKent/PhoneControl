"""Python-to-JS bridge API exposed to the pywebview frontend."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from .adb_service import AdbScrcpyService
from .device_store import DeviceStore
from .icon_cache import AppIconCache
from .window_host import Win32WindowHost


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
        window_host: Win32WindowHost | None = None,
        icon_cache: AppIconCache | None = None,
    ) -> None:
        self.service = service or AdbScrcpyService()
        self.store = store or DeviceStore()
        self.window_host = window_host or Win32WindowHost()
        self.icon_cache = icon_cache or AppIconCache()
        self._window: Any = None
        self._seen_online_ids: set[str] = set()
        self._is_fullscreen: bool = False

    def attach_window(self, window: Any, title: str = "") -> None:
        self._window = window
        if title:
            self.window_host.set_owner_title(title)

    def shutdown(self) -> None:
        self.window_host.stop_tracking()
        self.service.stop_all_mirrors()

    def get_initial_state(self) -> dict[str, Any]:
        try:
            settings = self.store.get_settings()
            if settings.get("always_on_top"):
                self.window_host.set_always_on_top(True)
            devices_res = self.scan_devices(trigger_auto_mirror=False)
            return _ok(
                {
                    "tools": self.service.get_tool_status(),
                    "settings": settings,
                    "devices": devices_res["data"]["devices"] if devices_res["ok"] else [],
                }
            )
        except Exception as exc:
            return _err(exc)

    def scan_devices(self, trigger_auto_mirror: bool = True) -> dict[str, Any]:
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
                        screen_width=int(dev.get("raw_width") or dev.get("screen_width") or 0),
                        screen_height=int(dev.get("raw_height") or dev.get("screen_height") or 0),
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
                            res = self.start_mirror(dev["serial"], title)
                            if res["ok"]:
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
                        "screen_width": int(dev.get("screen_width") or (saved.get("screen_width", 0) if saved else 0) or 1080),
                        "screen_height": int(dev.get("screen_height") or (saved.get("screen_height", 0) if saved else 0) or 2340),
                        "orientation": int(dev.get("orientation", 0)),
                        "show_touches": bool(dev.get("show_touches", False)),
                        "pointer_location": bool(dev.get("pointer_location", False)),
                        "screen_off": bool(dev.get("screen_off", False)),
                        "wifi_ip": dev.get("wifi_ip") or (saved.get("wifi_ip", "") if saved else ""),
                        "mirroring": bool(dev.get("mirroring", False)),
                        "saved": saved is not None,
                        "auto_mirror": bool(saved.get("auto_mirror", False)) if saved else False,
                        "last_seen": saved.get("last_seen", "") if saved else "",
                    }
                )

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
                        "screen_width": int(saved.get("screen_width", 0) or 1080),
                        "screen_height": int(saved.get("screen_height", 0) or 2340),
                        "orientation": 0,
                        "show_touches": False,
                        "pointer_location": False,
                        "screen_off": False,
                        "wifi_ip": saved.get("wifi_ip", ""),
                        "mirroring": False,
                        "saved": True,
                        "auto_mirror": bool(saved.get("auto_mirror", False)),
                        "last_seen": saved.get("last_seen", ""),
                    }
                )

            self._seen_online_ids = current_online_ids
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

    def start_mirror(
        self,
        serial: str,
        display_name: str = "",
        initial_slot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            settings = self.store.get_settings()
            embedded = bool(settings.get("embedded_workspace", True))
            title_token = f"PC_SLOT_{serial}" if embedded else f"{display_name or serial} — Phone Control"

            initial_rect: dict[str, int] | None = None
            if embedded and isinstance(initial_slot, dict):
                origin = self.window_host.get_client_origin()
                if origin:
                    initial_rect = {
                        "x": origin[0] + int(round(float(initial_slot.get("x", 0)))),
                        "y": origin[1] + int(round(float(initial_slot.get("y", 0)))),
                        "width": max(120, int(round(float(initial_slot.get("width", 360))))),
                        "height": max(200, int(round(float(initial_slot.get("height", 700))))),
                    }

            res = self.service.start_mirror(
                serial,
                title=title_token,
                settings=settings,
                borderless=embedded,
                initial_rect=initial_rect,
            )
            if embedded and res.get("pid"):
                threading.Thread(
                    target=self.window_host.register_mirror,
                    args=(serial, int(res["pid"]), title_token),
                    daemon=True,
                ).start()
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def stop_mirror(self, serial: str) -> dict[str, Any]:
        try:
            stopped = self.service.stop_mirror(serial)
            self.window_host.unregister_mirror(serial)
            return _ok({"serial": serial, "stopped": stopped})
        except Exception as exc:
            return _err(exc)

    def stop_all_mirrors(self) -> dict[str, Any]:
        try:
            for serial in self.service.get_active_mirrors():
                self.window_host.unregister_mirror(serial)
            self.service.stop_all_mirrors()
            return _ok({"stopped_all": True})
        except Exception as exc:
            return _err(exc)

    def sync_mirror_slots(self, slots: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            res = self.window_host.sync_slots(slots or [])
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def set_workspace_overlay_visible(self, visible: bool) -> dict[str, Any]:
        try:
            self.window_host.set_overlay_visible(bool(visible))
            return _ok({"visible": bool(visible)})
        except Exception as exc:
            return _err(exc)

    def set_always_on_top(self, enabled: bool) -> dict[str, Any]:
        try:
            val = bool(enabled)
            self.window_host.set_always_on_top(val)
            updated = self.store.update_settings({"always_on_top": val})
            return _ok({"always_on_top": val, "settings": updated})
        except Exception as exc:
            return _err(exc)

    def toggle_fullscreen(self) -> dict[str, Any]:
        try:
            if self._window and hasattr(self._window, "toggle_fullscreen"):
                self._window.toggle_fullscreen()
                self._is_fullscreen = not self._is_fullscreen
            return _ok({"fullscreen": self._is_fullscreen})
        except Exception as exc:
            return _err(exc)

    def set_display_power(self, serial: str, on: bool) -> dict[str, Any]:
        """Toggle physical display backlight cleanly, preferring native scrcpy Alt+O / Alt+Shift+O."""
        try:
            want_on = bool(on)
            # If the device has a docked scrcpy window, send native Alt+O / Alt+Shift+O directly
            # so turning the backlight OFF or back ON works instantaneously & reliably.
            if self.window_host.has_window(serial):
                sent = self.window_host.send_display_power_shortcut(serial, on=want_on)
                if sent:
                    self.service.mark_screen_off_state(serial, not want_on)
                    return _ok({"serial": serial, "screen_on": want_on, "screen_off": not want_on, "via": "scrcpy_shortcut"})
            res = self.service.set_display_power(serial, on=want_on)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def set_show_touches(self, serial: str, enabled: bool) -> dict[str, Any]:
        try:
            res = self.service.set_show_touches(serial, bool(enabled))
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def set_pointer_location(self, serial: str, enabled: bool) -> dict[str, Any]:
        try:
            res = self.service.set_pointer_location(serial, bool(enabled))
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def swipe(self, serial: str, direction: str, step: str = "") -> dict[str, Any]:
        try:
            chosen_step = step or self.store.get_settings().get("swipe_step", "medium")
            res = self.service.swipe(serial, direction, step=chosen_step)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def tap_center(self, serial: str) -> dict[str, Any]:
        try:
            res = self.service.tap_center(serial)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def open_app_drawer(self, serial: str) -> dict[str, Any]:
        try:
            res = self.service.open_app_drawer(serial)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def launch_quick_app(self, serial: str, app_key: str) -> dict[str, Any]:
        try:
            res = self.service.launch_quick_app(serial, app_key)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def list_apps(self, serial: str, force_refresh: bool = False) -> dict[str, Any]:
        try:
            apps = self.service.list_installed_apps(serial, force_refresh=bool(force_refresh))
            # Attach any already-cached icons immediately without blocking on network
            enriched = []
            for app in apps:
                cached_icon = self.icon_cache.get_cached(app["package"])
                enriched.append({**app, "icon": cached_icon or ""})
            return _ok({"apps": enriched})
        except Exception as exc:
            return _err(exc)

    def fetch_app_icons(self, packages: list[str]) -> dict[str, Any]:
        try:
            safe_pkgs = [str(p).strip() for p in (packages or [])[:60] if p]
            icons = self.icon_cache.resolve_batch(safe_pkgs, allow_network=True, max_workers=8)
            return _ok({"icons": icons})
        except Exception as exc:
            return _err(exc)

    def launch_package(self, serial: str, package_name: str) -> dict[str, Any]:
        try:
            res = self.service.launch_package(serial, package_name)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def force_stop_package(self, serial: str, package_name: str) -> dict[str, Any]:
        try:
            res = self.service.force_stop_package(serial, package_name)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def get_diagnostics(self, serial: str) -> dict[str, Any]:
        try:
            res = self.service.get_diagnostics(serial)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def set_battery_saver(self, serial: str, enabled: bool) -> dict[str, Any]:
        try:
            res = self.service.set_battery_saver(serial, bool(enabled))
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def clear_background_processes(self, serial: str) -> dict[str, Any]:
        try:
            res = self.service.clear_background_processes(serial)
            return _ok(res)
        except Exception as exc:
            return _err(exc)

    def launch_samsung_hw_test(self, serial: str) -> dict[str, Any]:
        try:
            res = self.service.launch_samsung_hw_test(serial)
            return _ok(res)
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
            if "always_on_top" in patch:
                self.window_host.set_always_on_top(bool(updated.get("always_on_top")))
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

            self.window_host.set_overlay_visible(False)
            try:
                selected = self._window.create_file_dialog(webview.FileDialog.OPEN)
            finally:
                self.window_host.set_overlay_visible(True)
            if not selected:
                return _ok({"cancelled": True})
            file_path = selected[0] if isinstance(selected, (list, tuple)) else str(selected)
            res = self.service.send_file(serial, file_path)
            return _ok(res)
        except Exception as exc:
            return _err(exc)
