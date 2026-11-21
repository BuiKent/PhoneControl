from __future__ import annotations

import json
from pathlib import Path

from phone_control.device_store import DEFAULT_SETTINGS, DeviceStore


def test_store_defaults_and_v2_settings_update(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    store = DeviceStore(cfg)

    settings = store.get_settings()
    assert settings["quality"] == DEFAULT_SETTINGS["quality"]
    assert settings["swipe_step"] == "medium"
    assert settings["zoom_mode"] == "fit"
    assert settings["sidebar_collapsed"] is False
    assert settings["screenshot_dir"]

    updated = store.update_settings(
        {
            "quality": "high",
            "turn_screen_off": True,
            "swipe_step": "long",
            "zoom_mode": "125",
            "sidebar_collapsed": True,
            "invalid_key": 123,
        }
    )
    assert updated["quality"] == "high"
    assert updated["swipe_step"] == "long"
    assert updated["zoom_mode"] == "125"
    assert updated["sidebar_collapsed"] is True
    assert "invalid_key" not in updated

    reloaded = DeviceStore(cfg)
    assert reloaded.get_settings()["zoom_mode"] == "125"
    assert reloaded.get_settings()["swipe_step"] == "long"


def test_store_migrates_v1_config_and_rejects_invalid_values(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    v1_payload = {
        "version": 1,
        "settings": {
            "quality": "lite",
            "stay_awake": False,
        },
        "devices": {
            "OLD01": {
                "id": "OLD01",
                "serial": "OLD01",
                "nickname": "Old Phone",
                "model": "SM-G977N",
                "wifi_ip": "192.168.1.50",
            }
        },
    }
    cfg.write_text(json.dumps(v1_payload), encoding="utf-8")

    store = DeviceStore(cfg)
    s = store.get_settings()
    assert s["quality"] == "lite"
    assert s["stay_awake"] is False
    assert s["zoom_mode"] == "fit"  # v2 default populated cleanly
    assert s["swipe_step"] == "medium"
    assert store.get_saved_devices()["OLD01"]["nickname"] == "Old Phone"

    after = store.update_settings({"quality": "ultra", "zoom_mode": "999", "swipe_step": "giant"})
    assert after["quality"] == "lite"
    assert after["zoom_mode"] == "fit"
    assert after["swipe_step"] == "medium"


def test_store_handles_corrupt_json(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json", encoding="utf-8")
    store = DeviceStore(cfg)
    assert store.get_settings()["quality"] == "balanced"


def test_device_upsert_rename_screen_dims_and_delete(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    store = DeviceStore(cfg)

    rec = store.upsert_device(
        "TESTDEV001",
        serial="TESTDEV001",
        model="SM-N986B",
        manufacturer="samsung",
        android_version="13",
        wifi_ip="192.168.1.25",
        screen_width=1080,
        screen_height=2316,
    )
    assert rec["screen_width"] == 1080
    assert rec["screen_height"] == 2316

    renamed = store.rename_device("TESTDEV001", "  My Primary Phone  ")
    assert renamed is not None
    assert renamed["nickname"] == "My Primary Phone"

    again = store.upsert_device("TESTDEV001", serial="TESTDEV001", model="SM-N986B")
    assert again["nickname"] == "My Primary Phone"
    assert again["screen_width"] == 1080

    assert store.set_device_auto_mirror("TESTDEV001", True)["auto_mirror"] is True
    assert store.delete_device("TESTDEV001") is True
    assert store.delete_device("TESTDEV001") is False
