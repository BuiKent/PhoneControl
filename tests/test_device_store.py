from __future__ import annotations

from pathlib import Path

from phone_control.device_store import DEFAULT_SETTINGS, DeviceStore


def test_store_defaults_and_settings_update(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    store = DeviceStore(cfg)

    settings = store.get_settings()
    assert settings["quality"] == DEFAULT_SETTINGS["quality"]
    assert settings["stay_awake"] is True
    assert settings["screenshot_dir"]

    updated = store.update_settings({"quality": "high", "turn_screen_off": True, "invalid_key": 123})
    assert updated["quality"] == "high"
    assert updated["turn_screen_off"] is True
    assert "invalid_key" not in updated

    # Reload from disk to confirm atomic persistence
    reloaded = DeviceStore(cfg)
    assert reloaded.get_settings()["quality"] == "high"
    assert reloaded.get_settings()["turn_screen_off"] is True


def test_store_rejects_invalid_quality_and_handles_corrupt_json(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text("{not valid json", encoding="utf-8")

    store = DeviceStore(cfg)
    assert store.get_settings()["quality"] == "balanced"
    updated = store.update_settings({"quality": "ultra_fake"})
    assert updated["quality"] == "balanced"


def test_device_upsert_rename_wifi_and_delete(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    store = DeviceStore(cfg)

    rec = store.upsert_device(
        "TESTDEV001",
        serial="TESTDEV001",
        model="SM-N986B",
        manufacturer="samsung",
        android_version="13",
        wifi_ip="192.168.1.25",
    )
    assert rec["model"] == "SM-N986B"
    assert rec["wifi_ip"] == "192.168.1.25"

    renamed = store.rename_device("TESTDEV001", "  My Primary Phone  ")
    assert renamed is not None
    assert renamed["nickname"] == "My Primary Phone"

    # Re-upserting preserves nickname
    again = store.upsert_device("TESTDEV001", serial="TESTDEV001", model="SM-N986B")
    assert again["nickname"] == "My Primary Phone"

    assert store.set_device_auto_mirror("TESTDEV001", True)["auto_mirror"] is True
    assert store.delete_device("TESTDEV001") is True
    assert store.delete_device("TESTDEV001") is False
    assert store.get_saved_devices() == {}
