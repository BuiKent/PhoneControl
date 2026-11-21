from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


UI_INDEX = Path(__file__).resolve().parent.parent / "phone_control" / "ui" / "index.html"


def test_ui_real_dom_interactions_and_zero_console_errors() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 460, "height": 820})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # Provide a faithful pywebview API bridge before page scripts run
        page.add_init_script(
            """
            window.__calls = [];
            window.__state = {
              mirroring: false,
              settings: {
                quality: "balanced",
                turn_screen_off: false,
                stay_awake: true,
                always_on_top: false,
                enable_audio: true,
                auto_mirror_saved: false
              },
              devices: [
                {
                  id: "TESTDEV001",
                  serial: "TESTDEV001",
                  state: "device",
                  online: true,
                  transport: "usb",
                  display_name: "Samsung SM-N986B",
                  nickname: "",
                  model: "SM-N986B",
                  manufacturer: "samsung",
                  android_version: "13",
                  battery: 88,
                  wifi_ip: "192.168.1.33",
                  mirroring: false,
                  saved: true,
                  auto_mirror: false
                },
                {
                  id: "OLD_S10",
                  serial: "OLD_S10",
                  state: "disconnected",
                  online: false,
                  transport: "wifi",
                  display_name: "Galaxy S10 5G",
                  nickname: "Galaxy S10 5G",
                  model: "SM-G977B",
                  manufacturer: "samsung",
                  android_version: "12",
                  battery: null,
                  wifi_ip: "192.168.1.40",
                  mirroring: false,
                  saved: true,
                  auto_mirror: false
                }
              ]
            };

            window.pywebview = {
              api: {
                async get_initial_state() {
                  window.__calls.push(["get_initial_state"]);
                  return {
                    ok: true,
                    data: {
                      tools: { adb_available: true, scrcpy_available: true },
                      settings: Object.assign({}, window.__state.settings),
                      devices: window.__state.devices.map(d => Object.assign({}, d))
                    }
                  };
                },
                async scan_devices(trigger) {
                  window.__calls.push(["scan_devices", trigger]);
                  return {
                    ok: true,
                    data: {
                      devices: window.__state.devices.map(d => Object.assign({}, d, { mirroring: d.id === "TESTDEV001" ? window.__state.mirroring : false })),
                      auto_mirrored: []
                    }
                  };
                },
                async start_mirror(serial, name) {
                  window.__calls.push(["start_mirror", serial, name]);
                  window.__state.mirroring = true;
                  return { ok: true, data: { serial, pid: 9999 } };
                },
                async stop_mirror(serial) {
                  window.__calls.push(["stop_mirror", serial]);
                  window.__state.mirroring = false;
                  return { ok: true, data: { serial, stopped: true } };
                },
                async take_screenshot(serial, label) {
                  window.__calls.push(["take_screenshot", serial, label]);
                  return {
                    ok: true,
                    data: {
                      path: "C:/Shots/shot1.png",
                      filename: "shot1.png",
                      size_bytes: 12345,
                      copied_to_clipboard: true
                    }
                  };
                },
                async send_action(serial, action) {
                  window.__calls.push(["send_action", serial, action]);
                  return { ok: true, data: { serial, action } };
                },
                async update_settings(patch) {
                  window.__calls.push(["update_settings", patch]);
                  Object.assign(window.__state.settings, patch);
                  return { ok: true, data: Object.assign({}, window.__state.settings) };
                },
                async rename_device(id, nickname) {
                  window.__calls.push(["rename_device", id, nickname]);
                  const d = window.__state.devices.find(x => x.id === id);
                  if (d) { d.nickname = nickname; d.display_name = nickname; }
                  return { ok: true, data: d };
                },
                async connect_wifi(addr) {
                  window.__calls.push(["connect_wifi", addr]);
                  return { ok: true, data: { target: addr } };
                },
                async open_screenshot_folder() {
                  window.__calls.push(["open_screenshot_folder"]);
                  return { ok: true, data: {} };
                },
                async open_file(path) {
                  window.__calls.push(["open_file", path]);
                  return { ok: true, data: { path } };
                }
              }
            };
            """
        )

        page.goto(UI_INDEX.as_uri(), wait_until="domcontentloaded")
        page.wait_for_selector(".device-card")

        # 1. Both online and saved-disconnected devices render; online is selected by default
        assert page.locator(".device-card").count() == 2
        assert "Samsung SM-N986B" in page.locator("#selectedDeviceBadge").inner_text()
        assert page.locator("#btnToggleMirror").is_enabled()

        # 2. Real DOM click to start & stop scrcpy mirror
        page.locator("#btnToggleMirror").click()
        page.wait_for_function("() => document.getElementById('mirrorBtnLabel').textContent.includes('Dừng')")
        assert "Đang chiếu" in page.locator("#mirrorBtnLabel").inner_text()

        page.locator("#btnToggleMirror").click()
        page.wait_for_function("() => document.getElementById('mirrorBtnLabel').textContent.includes('Mở màn hình')")

        # 3. Real DOM click on Screenshot button + status action button
        page.locator("#btnScreenshot").click()
        page.wait_for_function("() => document.getElementById('statusMessage').textContent.includes('shot1.png')")
        assert page.locator("#btnStatusAction").is_visible()
        page.locator("#btnStatusAction").click()

        # 4. Real DOM clicks on hardware control pad buttons
        page.locator(".pad-btn[data-action='back']").click()
        page.locator(".pad-btn[data-action='home']").click()
        page.locator(".pad-btn[data-action='vol_up']").click()
        page.locator(".pad-btn[data-action='rotate']").click()

        # 5. Real DOM click on quality toggle and checkbox setting
        page.locator(".seg-btn[data-quality='high']").click()
        page.locator("#chkTurnScreenOff").click()

        # 6. Real DOM click to switch selection to disconnected saved device -> controls disable
        page.locator(".device-card[data-device-id='OLD_S10']").click()
        assert page.locator("#btnToggleMirror").is_disabled()
        assert page.locator(".pad-btn[data-action='home']").is_disabled()

        # Switch back to online device
        page.locator(".device-card[data-device-id='TESTDEV001']").click()
        assert page.locator("#btnToggleMirror").is_enabled()

        # 7. Real DOM modal flow: Rename device
        page.locator(".device-card[data-device-id='TESTDEV001'] button[aria-label^='Đổi tên']").click()
        assert page.locator("#renameModal").is_visible()
        page.locator("#inputDeviceNickname").fill("Note20 Ultra Chính")
        page.locator("#btnSaveRename").click()
        page.wait_for_function("() => document.getElementById('selectedDeviceBadge').textContent.includes('Note20 Ultra Chính')")

        # 8. Real DOM modal flow: Add Wi-Fi modal + tabs + connect
        page.locator("#btnOpenWifiModal").click()
        assert page.locator("#wifiModal").is_visible()
        page.locator(".tab-btn[data-tab='pair']").click()
        assert page.locator("#tab-pair").is_visible()
        page.locator(".tab-btn[data-tab='connect']").click()
        page.locator("#inputWifiAddr").fill("192.168.1.99:5555")
        page.locator("#btnDoWifiConnect").click()
        page.wait_for_function("() => document.getElementById('wifiModal').classList.contains('hidden')")

        calls = page.evaluate("() => window.__calls")
        called_methods = [c[0] for c in calls]
        assert "start_mirror" in called_methods
        assert "stop_mirror" in called_methods
        assert "take_screenshot" in called_methods
        assert "open_file" in called_methods
        assert "send_action" in called_methods
        assert "update_settings" in called_methods
        assert "rename_device" in called_methods
        assert "connect_wifi" in called_methods

        # Verify zero runtime JS errors
        assert console_errors == [], f"Console errors: {console_errors}"
        assert page_errors == [], f"Page errors: {page_errors}"
        browser.close()
