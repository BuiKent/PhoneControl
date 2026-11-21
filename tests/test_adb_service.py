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
    compute_swipe_coords,
    oriented_dimensions,
    parse_adb_devices,
    parse_battery_info,
    parse_battery_level,
    parse_meminfo,
    parse_orientation,
    parse_recent_crashes,
    parse_scrcpy_app_list,
    parse_storage_df,
    parse_wifi_ip,
    parse_wifi_signal,
    parse_wm_size,
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


def test_parse_battery_wifi_wm_size_and_app_list() -> None:
    bat_out = "Current Battery Service state:\n  AC powered: false\n  level: 84\n  scale: 100\n"
    assert parse_battery_level(bat_out) == 84
    assert parse_battery_level("no level here") is None

    ip_out = "192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.42 metric 600"
    assert parse_wifi_ip(ip_out) == "192.168.1.42"
    assert parse_wifi_ip("inet 127.0.0.1/8 scope host lo") == ""

    # Samsung FHD+ mode reports both Physical and Override size; Override must win
    wm_out = "Physical size: 1440x3040\nOverride size: 1080x2280\n"
    assert parse_wm_size(wm_out) == (1080, 2280)
    assert parse_wm_size("Physical size: 1080x2400\n") == (1080, 2400)
    assert parse_wm_size("no size") is None

    app_out = """[server] INFO: List of apps:
 * Bộ sưu tập                     com.sec.android.gallery3d
 - Zalo                           com.zing.zalo
 * Chrome                         com.android.chrome
"""
    apps = parse_scrcpy_app_list(app_out)
    assert len(apps) == 3
    assert [a["package"] for a in apps] == [
        "com.sec.android.gallery3d",
        "com.android.chrome",
        "com.zing.zalo",
    ]
    assert apps[2]["system"] is False


def test_compute_swipe_coords_all_directions_and_steps() -> None:
    x1, y1, x2, y2, dur_short = compute_swipe_coords(1080, 2280, "up", "short")
    _, y1_long, _, y2_long, dur_long = compute_swipe_coords(1080, 2280, "up", "long")
    assert x1 == x2 == 540
    assert y1 > y2  # finger moves upward
    assert (y1_long - y2_long) > (y1 - y2)
    assert dur_long > dur_short

    dx1, dy1, dx2, dy2, _ = compute_swipe_coords(1080, 2280, "down", "medium")
    assert dx1 == dx2 and dy1 < dy2

    lx1, ly1, lx2, ly2, _ = compute_swipe_coords(1080, 2280, "left", "medium")
    assert ly1 == ly2 and lx1 > lx2

    rx1, ry1, rx2, ry2, _ = compute_swipe_coords(1080, 2280, "right", "medium")
    assert ry1 == ry2 and rx1 < rx2

    with pytest.raises(ValueError, match="Hướng vuốt"):
        compute_swipe_coords(1080, 2280, "diagonal")


def test_build_scrcpy_args_borderless_and_initial_rect(tmp_path: Path) -> None:
    scrcpy_exe = tmp_path / "scrcpy.exe"
    args = build_scrcpy_args(
        scrcpy_exe,
        "TESTDEV001",
        title="PC_SLOT_TESTDEV001",
        settings={
            "quality": "lite",
            "stay_awake": True,
            "turn_screen_off": True,
            "always_on_top": True,
            "enable_audio": False,
        },
        borderless=True,
        initial_rect={"x": 320, "y": 80, "width": 360, "height": 760},
    )
    assert "--window-borderless" in args
    assert "--always-on-top" not in args  # owned borderless mode avoids stealing global z-order
    assert "--window-x=320" in args
    assert "--window-width=360" in args
    assert "--max-fps=30" in args
    assert "--no-audio" in args


def test_set_display_power_off_uses_headless_scrcpy_helper(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    scrcpy_exe = tmp_path / "scrcpy.exe"
    adb_exe.write_bytes(b"")
    scrcpy_exe.write_bytes(b"")

    fake_proc = MagicMock()
    fake_proc.poll.return_value = None
    popen = MagicMock(return_value=fake_proc)
    runner = MagicMock(return_value=_completed(stdout=""))

    svc = AdbScrcpyService(
        tools=ToolPaths(adb=adb_exe, scrcpy=scrcpy_exe),
        runner=runner,
        popen_factory=popen,
    )

    off_res = svc.set_display_power("TESTDEV001", on=False)
    assert off_res["screen_on"] is False
    helper_cmd = popen.call_args[0][0]
    assert "--no-window" in helper_cmd
    assert "--no-video" in helper_cmd
    assert "--no-audio" in helper_cmd
    assert "--turn-screen-off" in helper_cmd
    fake_proc.terminate.assert_called_once()

    on_res = svc.set_display_power("TESTDEV001", on=True)
    assert on_res["screen_on"] is True
    assert runner.call_args[0][0][-1] == "224"


def test_quick_apps_fallback_and_package_validation(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    runner = MagicMock(
        side_effect=[
            _completed(stdout="Error: Activity not started, unable to resolve Intent"),
            _completed(stdout="Events injected: 1"),
            _completed(stdout="Events injected: 1"),
        ]
    )
    svc = AdbScrcpyService(tools=ToolPaths(adb=adb_exe, scrcpy=None), runner=runner)

    res = svc.launch_quick_app("TESTDEV001", "gallery")
    assert res["app_key"] == "gallery"
    assert runner.call_count == 2  # fell back to Samsung gallery3d

    pkg_res = svc.launch_package("TESTDEV001", "com.android.chrome")
    assert pkg_res["package"] == "com.android.chrome"

    with pytest.raises(ValueError, match="Tên gói ứng dụng"):
        svc.launch_package("TESTDEV001", "com.evil; rm -rf /")


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


def test_send_action_show_touches_and_send_file(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"apk")
    doc = tmp_path / "note.pdf"
    doc.write_bytes(b"pdf")

    runner = MagicMock(
        side_effect=[
            _completed(stdout=""),
            _completed(stdout=""),
            _completed(stdout="Success"),
            _completed(stdout="1 file pushed"),
        ]
    )
    svc = AdbScrcpyService(tools=ToolPaths(adb=adb_exe, scrcpy=None), runner=runner)

    assert svc.send_action("TESTDEV001", "home")["action"] == "home"
    assert svc.set_show_touches("TESTDEV001", True)["show_touches"] is True
    assert svc.send_file("TESTDEV001", str(apk))["mode"] == "apk"
    assert svc.send_file("TESTDEV001", str(doc))["mode"] == "push"

    with pytest.raises(ValueError, match="không hợp lệ"):
        svc.send_action("TESTDEV001", "explode")


def test_orientation_and_diagnostics_parsers() -> None:
    assert parse_orientation("      SurfaceOrientation: 1\n") == 1
    assert parse_orientation("    mCurrentOrientation=3\n") == 3
    assert oriented_dimensions(1080, 2280, 0) == (1080, 2280)
    assert oriented_dimensions(1080, 2280, 1) == (2280, 1080)

    bat = parse_battery_info(
        "  status: 2\n  health: 2\n  level: 65\n  voltage: 4073\n  temperature: 353\n  technology: Li-ion\n"
    )
    assert bat["level"] == 65
    assert bat["temperature_c"] == 35.3
    assert bat["voltage_v"] == 4.07
    assert bat["health_label"] == "Tốt"
    assert bat["status_label"] == "Đang sạc"

    mem = parse_meminfo("MemTotal:        8000000 kB\nMemAvailable:    3000000 kB\n")
    assert mem["used_pct"] == 62

    sto = parse_storage_df("/dev/block/sda33 209715200 52428800 157286400 25% /data\n")
    assert sto["used_pct"] == 25 and sto["free_gb"] == 150.0

    wifi = parse_wifi_signal('0 0 "Sweethome 2g" 20:be:b4:20:4f:f6 rssi=-55 link=195')
    assert wifi["ssid"] == "Sweethome 2g"
    assert wifi["rssi_dbm"] == -55
    assert wifi["link_mbps"] == 195
    assert wifi["quality"] == "Rất mạnh"

    crashes = parse_recent_crashes(
        "2026-11-21 19:10:00 data_app_crash (text, 1234 bytes) com.example.broken\n"
        "2026-11-21 19:20:00 data_app_anr (text, 2000 bytes) com.example.frozen\n"
    )
    assert len(crashes) == 2
    assert crashes[0]["package"] == "com.example.frozen"
    assert "ANR" in crashes[0]["type"]


def test_rotate_updates_effective_landscape_dimensions(tmp_path: Path) -> None:
    adb_exe = tmp_path / "adb.exe"
    adb_exe.write_bytes(b"")
    runner = MagicMock(
        side_effect=[
            _completed(stdout="SurfaceOrientation: 0\n"),  # get_current_orientation
            _completed(stdout=""),  # accelerometer_rotation 0
            _completed(stdout=""),  # user_rotation 1
            _completed(stdout="MFR=samsung\nMDL=SM-G977N\nVER=12\nSER=TESTDEV001\nPhysical size: 1440x3040\nOverride size: 1080x2280\nSurfaceOrientation: 1\n"),
            _completed(stdout="level: 70\n"),
        ]
    )
    svc = AdbScrcpyService(tools=ToolPaths(adb=adb_exe, scrcpy=None), runner=runner)
    res = svc.send_action("TESTDEV001", "rotate")
    assert res["orientation"] == 1
    assert res["screen_width"] == 2280
    assert res["screen_height"] == 1080

