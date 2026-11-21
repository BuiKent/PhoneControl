from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from phone_control.adb_service import (
    PNG_SIGNATURE,
    AdbScrcpyService,
    ToolPaths,
    build_scrcpy_args,
    parse_adb_devices,
    parse_battery_level,
    parse_wifi_ip,
)


def _completed(stdout: str | bytes = "", stderr: str | bytes = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["adb"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_parse_adb_devices_usb_wifi_and_unauthorized() -> None:
    raw = """* daemon started successfully
List of devices attached
TESTDEV001             device product:c2sxxx model:SM_N986B device:c2s transport_id:1
192.168.1.20:5555      device product:star2lte model:SM_G965F device:star2lte transport_id:2
ZY2244FAKE             unauthorized transport_id:3
"""
    devices = parse_adb_devices(raw)
    assert len(devices) == 3
    assert devices[0]["serial"] == "TESTDEV001"
    assert devices[0]["model"] == "SM N986B"
    assert devices[0]["transport"] == "usb"
    assert devices[1]["transport"] == "wifi"
    assert devices[2]["state"] == "unauthorized"


def test_parse_battery_and_wifi_ip() -> None:
    bat_out = "Current Battery Service state:\n  AC powered: false\n  level: 84\n  scale: 100\n"
    assert parse_battery_level(bat_out) == 84
    assert parse_battery_level("no level here") is None

    ip_out = "192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.42 metric 600"
    assert parse_wifi_ip(ip_out) == "192.168.1.42"
    assert parse_wifi_ip("inet 127.0.0.1/8 scope host lo") == ""


def test_build_scrcpy_args_respects_profiles_and_flags(tmp_path: Path) -> None:
    scrcpy_exe = tmp_path / "scrcpy.exe"
    args = build_scrcpy_args(
        scrcpy_exe,
        "TESTDEV001",
        title="Samsung Note20",
        settings={
            "quality": "lite",
            "stay_awake": True,
            "turn_screen_off": True,
            "always_on_top": True,
            "enable_audio": False,
        },
    )
    assert "-s" in args and "TESTDEV001" in args
    assert "--video-bit-rate=4M" in args
    assert "--max-fps=30" in args
    assert "--max-size=1280" in args
    assert "--turn-screen-off" in args
    assert "--always-on-top" in args
    assert "--no-audio" in args


def test_screenshot_validates_png_saves_and_copies_clipboard(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    scrcpy_exe = tmp_path / "scrcpy.exe"
    adb_exe.write_bytes(b"")
    scrcpy_exe.write_bytes(b"")

    fake_png = PNG_SIGNATURE + b"fakepngpayload"
    runner = MagicMock(return_value=_completed(stdout=fake_png))
    clipboard = MagicMock(return_value=True)

    svc = AdbScrcpyService(
        tools=ToolPaths(adb=adb_exe, scrcpy=scrcpy_exe),
        runner=runner,
        clipboard_fn=clipboard,
    )
    out_dir = tmp_path / "shots"
    res = svc.take_screenshot("TESTDEV001", output_dir=out_dir, device_label="Samsung:Note20/Ultra")
    saved = Path(res["path"])
    assert saved.exists()
    assert saved.read_bytes() == fake_png
    assert ":" not in saved.name
    assert res["copied_to_clipboard"] is True
    clipboard.assert_called_once_with(fake_png)


def test_screenshot_rejects_corrupt_or_secure_payload(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    svc = AdbScrcpyService(
        tools=ToolPaths(adb=adb_exe, scrcpy=None),
        runner=MagicMock(return_value=_completed(stdout=b"not a png")),
        clipboard_fn=MagicMock(return_value=False),
    )
    with pytest.raises(RuntimeError, match="FLAG_SECURE"):
        svc.take_screenshot("TESTDEV001", output_dir=tmp_path)


def test_send_action_keyevents_and_invalid_action(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    runner = MagicMock(return_value=_completed(stdout=""))
    svc = AdbScrcpyService(tools=ToolPaths(adb=adb_exe, scrcpy=None), runner=runner)

    res = svc.send_action("TESTDEV001", "home")
    assert res["action"] == "home"
    called_cmd = runner.call_args[0][0]
    assert called_cmd[-4:] == ["shell", "input", "keyevent", "3"]

    with pytest.raises(ValueError, match="không hợp lệ"):
        svc.send_action("TESTDEV001", "explode")


def test_send_file_apk_vs_regular(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"apk")
    doc = tmp_path / "note.pdf"
    doc.write_bytes(b"pdf")

    runner = MagicMock(side_effect=[_completed(stdout="Success"), _completed(stdout="1 file pushed")])
    svc = AdbScrcpyService(tools=ToolPaths(adb=adb_exe, scrcpy=None), runner=runner)

    r1 = svc.send_file("TESTDEV001", str(apk))
    assert r1["mode"] == "apk"
    assert "install" in runner.call_args_list[0][0][0]

    r2 = svc.send_file("TESTDEV001", str(doc))
    assert r2["mode"] == "push"
    assert "push" in runner.call_args_list[1][0][0]
