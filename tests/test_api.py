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
            "wifi_ip": "192.168.1.50",
            "mirroring": False,
        }
    ]
    svc.start_mirror.return_value = {"serial": "TESTDEV001", "pid": 4321, "already_running": False}

    api = PhoneControlAPI(service=svc, store=store)

    # First scan sees newly connected saved device -> auto-mirrors once
    res1 = api.scan_devices(trigger_auto_mirror=True)
    assert res1["ok"] is True
    assert res1["data"]["auto_mirrored"] == ["TESTDEV001"]
    devices = res1["data"]["devices"]
    assert len(devices) == 2
    assert devices[0]["id"] == "TESTDEV001"
    assert devices[0]["online"] is True
    assert devices[0]["mirroring"] is True
    assert devices[1]["id"] == "OLD_PHONE"
    assert devices[1]["state"] == "disconnected"
    svc.start_mirror.assert_called_once()

    # Second scan while still online should NOT auto-mirror again even if user closed scrcpy
    svc.list_devices.return_value[0]["mirroring"] = False
    res2 = api.scan_devices(trigger_auto_mirror=True)
    assert res2["data"]["auto_mirrored"] == []
    svc.start_mirror.assert_called_once()


def test_api_rename_and_delete_device(tmp_path: Path) -> None:
    store = DeviceStore(tmp_path / "config.json")
    store.upsert_device("DEV1", serial="DEV1", model="Pixel 8")
    api = PhoneControlAPI(service=MagicMock(), store=store)

    r = api.rename_device("DEV1", "Máy phụ")
    assert r["ok"] is True
    assert r["data"]["nickname"] == "Máy phụ"

    missing = api.rename_device("UNKNOWN", "X")
    assert missing["ok"] is False

    d = api.delete_saved_device("DEV1")
    assert d["ok"] is True
    assert d["data"]["deleted"] is True
