from __future__ import annotations

from phone_control.window_host import Win32WindowHost, find_window_by_title


def test_find_window_by_title_returns_none_for_missing_window() -> None:
    # Regression test: Win32 FindWindowW returns NULL -> ctypes HWND becomes None
    assert find_window_by_title("__PHONE_CONTROL_NON_EXISTENT_WINDOW_99999__") is None


def test_window_host_set_owner_title_before_window_exists_does_not_crash() -> None:
    host = Win32WindowHost()
    host.set_owner_title("__PHONE_CONTROL_NON_EXISTENT_WINDOW_99999__")
    res = host.sync_slots([{"serial": "TESTDEV001", "x": 100, "y": 50, "width": 320, "height": 640}])
    assert res["synced"] == 1
    assert host.has_window("TESTDEV001") is False
