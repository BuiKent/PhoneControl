from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from phone_control.api import PhoneControlAPI
from phone_control.device_store import DeviceStore


def test_api_merges_online_and_saved_devices_and_auto_mirrors_once(tmp_path: Path) -> None:
    store = DeviceStore(tmp_path / "config.json")
    store.upsert_device(
        "OLD_PHONE",
        serial="OLD_PHONE",
        model="SM-G977B",
        manufacturer="samsung",
        wifi_ip="192.168.1.99",
    )
    store.upsert_device(
        "TESTDEV001",
        serial="TESTDEV001",
        model="SM-N986B",
        manufacturer="samsung",
    )
    store.update_settings({"auto_mirror_saved": True})

    svc = MagicMock()
    svc.list_devices.return_value = [
        {
            "serial": "TESTDEV001",
            "hardware_serial": "TESTDEV001",
            "state": "device",
            "transport": "usb",
            "model": "SM-N986B",
            "manufacturer": "samsung",
            "android_version": "13",
            "battery": 76,
            "screen_width": 1080,
            "screen_height": 2316,
            "show_touches": True,
            "wifi_ip": "192.168.1.50",
            "mirroring": False,
        }
    ]
    svc.start_mirror.return_value = {"serial": "TESTDEV001", "pid": 4321, "already_running": False}

    host = MagicMock()
    host.get_client_origin.return_value = (100, 100)
    api = PhoneControlAPI(service=svc, store=store, window_host=host)

    res1 = api.scan_devices(trigger_auto_mirror=True)
    assert res1["ok"] is True
    assert res1["data"]["auto_mirrored"] == ["TESTDEV001"]
    devices = res1["data"]["devices"]
    assert len(devices) == 2
    assert devices[0]["id"] == "TESTDEV001"
    assert devices[0]["show_touches"] is True
    assert devices[0]["mirroring"] is True
    svc.start_mirror.assert_called_once()

    svc.list_devices.return_value[0]["mirroring"] = False
    res2 = api.scan_devices(trigger_auto_mirror=True)
    assert res2["data"]["auto_mirrored"] == []
    svc.start_mirror.assert_called_once()


def test_api_v2_controls_and_slot_sync(tmp_path: Path) -> None:
    store = DeviceStore(tmp_path / "config.json")
    store.upsert_device("DEV1", serial="DEV1", model="Galaxy S10 5G")
    svc = MagicMock()
    svc.set_display_power.return_value = {"serial": "DEV1", "screen_on": False}
    svc.swipe.return_value = {"serial": "DEV1", "direction": "up", "step": "medium"}
    svc.launch_quick_app.return_value = {"serial": "DEV1", "app_key": "camera"}
    svc.set_show_touches.return_value = {"serial": "DEV1", "show_touches": True}
    host = MagicMock()
    host.sync_slots.return_value = {"synced": 1, "attached": 1}

    api = PhoneControlAPI(service=svc, store=store, window_host=host)

    assert api.set_display_power("DEV1", False)["ok"] is True
    assert api.swipe("DEV1", "up")["ok"] is True
    assert api.launch_quick_app("DEV1", "camera")["ok"] is True
    assert api.set_show_touches("DEV1", True)["ok"] is True
    assert api.sync_mirror_slots([{"serial": "DEV1", "x": 320, "y": 50, "width": 350, "height": 720}])["ok"] is True

    r = api.rename_device("DEV1", "Máy phụ")
    assert r["ok"] is True and r["data"]["nickname"] == "Máy phụ"
    assert api.rename_device("UNKNOWN", "X")["ok"] is False
    assert api.delete_saved_device("DEV1")["data"]["deleted"] is True
