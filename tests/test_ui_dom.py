from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


UI_INDEX = Path(__file__).resolve().parent.parent / "phone_control" / "ui" / "index.html"


def test_ui_v2_1_grid_apps_toggle_power_rotate_phone_only_and_diagnostics() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 820})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        page.add_init_script(
            """
            window.__calls = [];
            window.__state = {
              mirroring: {},
              screenOff: {},
              orientation: { TESTDEV001: 0, TESTDEV002: 0 },
              settings: {
                quality: "balanced",
                turn_screen_off: false,
                stay_awake: true,
                always_on_top: false,
                enable_audio: true,
                auto_mirror_saved: false,
                swipe_step: "medium",
                zoom_mode: "fit",
                sidebar_collapsed: false,
                embedded_workspace: true
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
                  screen_width: 1080,
                  screen_height: 2316,
                  orientation: 0,
                  show_touches: false,
                  pointer_location: false,
                  screen_off: false,
                  wifi_ip: "192.168.1.33",
                  mirroring: false,
                  saved: true,
                  auto_mirror: false
                },
                {
                  id: "TESTDEV002",
                  serial: "TESTDEV002",
                  state: "device",
                  online: true,
                  transport: "usb",
                  display_name: "Samsung SM-G977N",
                  nickname: "Galaxy S10 5G",
                  model: "SM-G977N",
                  manufacturer: "samsung",
                  android_version: "12",
                  battery: 72,
                  screen_width: 1080,
                  screen_height: 2280,
                  orientation: 0,
                  show_touches: false,
                  pointer_location: false,
                  screen_off: false,
                  wifi_ip: "192.168.1.40",
                  mirroring: false,
                  saved: true,
                  auto_mirror: false
                }
              ]
            };

            function snapshotDevices() {
              return window.__state.devices.map(d => {
                const orient = window.__state.orientation[d.serial] || 0;
                const w = orient === 1 ? Math.max(d.screen_width, d.screen_height) : Math.min(d.screen_width, d.screen_height);
                const h = orient === 1 ? Math.min(d.screen_width, d.screen_height) : Math.max(d.screen_width, d.screen_height);
                return Object.assign({}, d, {
                  orientation: orient,
                  screen_width: w,
                  screen_height: h,
                  mirroring: Boolean(window.__state.mirroring[d.serial]),
                  screen_off: Boolean(window.__state.screenOff[d.serial])
                });
              });
            }

            window.pywebview = {
              api: {
                async get_initial_state() {
                  window.__calls.push(["get_initial_state"]);
                  return {
                    ok: true,
                    data: {
                      tools: { adb_available: true, scrcpy_available: true },
                      settings: Object.assign({}, window.__state.settings),
                      devices: snapshotDevices()
                    }
                  };
                },
                async scan_devices(trigger) {
                  window.__calls.push(["scan_devices", trigger]);
                  return { ok: true, data: { devices: snapshotDevices(), auto_mirrored: [] } };
                },
                async start_mirror(serial, name, slot) {
                  window.__calls.push(["start_mirror", serial, name, slot]);
                  window.__state.mirroring[serial] = true;
                  return { ok: true, data: { serial, pid: 9999 } };
                },
                async stop_mirror(serial) {
                  window.__calls.push(["stop_mirror", serial]);
                  window.__state.mirroring[serial] = false;
                  return { ok: true, data: { serial, stopped: true } };
                },
                async sync_mirror_slots(slots) {
                  window.__calls.push(["sync_mirror_slots", slots]);
                  return { ok: true, data: { synced: slots.length } };
                },
                async set_always_on_top(enabled) {
                  window.__calls.push(["set_always_on_top", enabled]);
                  window.__state.settings.always_on_top = enabled;
                  return { ok: true, data: { always_on_top: enabled } };
                },
                async set_display_power(serial, on) {
                  window.__calls.push(["set_display_power", serial, on]);
                  window.__state.screenOff[serial] = !on;
                  return { ok: true, data: { serial, screen_on: on, screen_off: !on } };
                },
                async set_show_touches(serial, enabled) {
                  window.__calls.push(["set_show_touches", serial, enabled]);
                  const d = window.__state.devices.find(x => x.serial === serial);
                  if (d) d.show_touches = enabled;
                  return { ok: true, data: { serial, show_touches: enabled } };
                },
                async set_pointer_location(serial, enabled) {
                  window.__calls.push(["set_pointer_location", serial, enabled]);
                  return { ok: true, data: { serial, pointer_location: enabled } };
                },
                async swipe(serial, direction, step) {
                  window.__calls.push(["swipe", serial, direction, step]);
                  return { ok: true, data: { serial, direction, step } };
                },
                async send_action(serial, action) {
                  window.__calls.push(["send_action", serial, action]);
                  if (action === "rotate") {
                    const next = window.__state.orientation[serial] === 1 ? 0 : 1;
                    window.__state.orientation[serial] = next;
                    return {
                      ok: true,
                      data: {
                        serial,
                        action: "rotate",
                        orientation: next,
                        screen_width: next === 1 ? 2316 : 1080,
                        screen_height: next === 1 ? 1080 : 2316
                      }
                    };
                  }
                  return { ok: true, data: { serial, action } };
                },
                async launch_quick_app(serial, appKey) {
                  window.__calls.push(["launch_quick_app", serial, appKey]);
                  return { ok: true, data: { serial, app_key: appKey } };
                },
                async list_apps(serial) {
                  window.__calls.push(["list_apps", serial]);
                  return {
                    ok: true,
                    data: {
                      apps: [
                        { name: "Bộ sưu tập", package: "com.sec.android.gallery3d", system: true, icon: "" },
                        { name: "Chrome", package: "com.android.chrome", system: true, icon: "" },
                        { name: "Zalo", package: "com.zing.zalo", system: false, icon: "" }
                      ]
                    }
                  };
                },
                async fetch_app_icons(packages) {
                  window.__calls.push(["fetch_app_icons", packages]);
                  const tinyPng = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
                  return { ok: true, data: { icons: { "com.zing.zalo": tinyPng } } };
                },
                async launch_package(serial, pkg) {
                  window.__calls.push(["launch_package", serial, pkg]);
                  return { ok: true, data: { serial, package: pkg } };
                },
                async get_diagnostics(serial) {
                  window.__calls.push(["get_diagnostics", serial]);
                  return {
                    ok: true,
                    data: {
                      serial,
                      battery: { level: 65, temperature_c: 35.3, voltage_v: 4.07, health_code: 2, health_label: "Tốt", status_label: "Đang sạc", technology: "Li-ion" },
                      memory: { total_gb: 7.1, used_gb: 4.0, available_gb: 3.1, used_pct: 56 },
                      storage: { total_gb: 228.6, used_gb: 57.3, free_gb: 171.3, used_pct: 25 },
                      wifi: { ssid: "Sweethome", rssi_dbm: -55, link_mbps: 195, quality: "Rất mạnh" },
                      ping_ms: 14.2,
                      power_save: false,
                      pointer_location: false,
                      has_samsung_hwtest: true,
                      crashes: [{ timestamp: "2026-11-21 19:20:00", type: "Crash (Văng)", package: "com.example.broken" }]
                    }
                  };
                },
                async set_battery_saver(serial, enabled) {
                  window.__calls.push(["set_battery_saver", serial, enabled]);
                  return { ok: true, data: { serial, power_save: enabled } };
                },
                async clear_background_processes(serial) {
                  window.__calls.push(["clear_background_processes", serial]);
                  return { ok: true, data: { serial, cleared: true } };
                },
                async launch_samsung_hw_test(serial) {
                  window.__calls.push(["launch_samsung_hw_test", serial]);
                  return { ok: true, data: { serial, launched: true } };
                },
                async force_stop_package(serial, pkg) {
                  window.__calls.push(["force_stop_package", serial, pkg]);
                  return { ok: true, data: { serial, package: pkg } };
                },
                async take_screenshot(serial, label) {
                  window.__calls.push(["take_screenshot", serial, label]);
                  return { ok: true, data: { path: "C:/Shots/shot1.png", filename: "shot1.png", copied_to_clipboard: true } };
                },
                async update_settings(patch) {
                  window.__calls.push(["update_settings", patch]);
                  Object.assign(window.__state.settings, patch);
                  return { ok: true, data: Object.assign({}, window.__state.settings) };
                },
                async connect_wifi(addr) {
                  window.__calls.push(["connect_wifi", addr]);
                  return { ok: true, data: { target: addr } };
                },
                async toggle_fullscreen() {
                  window.__calls.push(["toggle_fullscreen"]);
                  return { ok: true, data: { fullscreen: true } };
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
        page.wait_for_selector(".device-item")

        # 1. Start mirroring 1 phone, then test Rotate -> viewport MUST become landscape (width > height)!
        page.locator("#btnToggleMirror").click()
        page.wait_for_selector(".phone-slot-viewport")
        box_portrait = page.locator(".phone-slot-viewport").first.bounding_box()
        assert box_portrait["height"] > box_portrait["width"]

        page.locator("#btnRotate").click()
        page.wait_for_function("() => document.querySelector('.phone-slot').dataset.landscape === 'true'")
        box_landscape = page.locator(".phone-slot-viewport").first.bounding_box()
        assert box_landscape["width"] > box_landscape["height"]
        assert page.locator("#btnRotate").get_attribute("aria-pressed") == "true"

        # Rotate back to portrait
        page.locator("#btnRotate").click()
        page.wait_for_function("() => document.querySelector('.phone-slot').dataset.landscape === 'false'")

        # 2. Unified Display Power Toggle (OFF -> lit active-amber -> ON -> unlit)
        page.locator("#btnToggleScreenOff").click()
        page.wait_for_function("() => document.getElementById('btnToggleScreenOff').getAttribute('aria-pressed') === 'true'")
        assert "Màn ĐT: Tắt" in page.locator("#sidebarScreenOffLabel").inner_text()
        assert "active-amber" in page.locator("#btnTopScreenOff").get_attribute("class")

        page.locator("#btnToggleScreenOff").click()
        page.wait_for_function("() => document.getElementById('btnToggleScreenOff').getAttribute('aria-pressed') === 'false'")
        assert "Tắt màn ĐT" in page.locator("#sidebarScreenOffLabel").inner_text()

        # 3. Always-On-Top toggle synced across Topbar & Sidebar
        page.locator("#btnAlwaysOnTop").click()
        page.wait_for_function("() => document.getElementById('btnAlwaysOnTop').getAttribute('aria-pressed') === 'true'")
        assert page.locator("#btnSideAlwaysOnTop").get_attribute("aria-pressed") == "true"

        # 4. Phone-Only mode (hide all toolbars, keep 28px recovery miniStrip) & exit
        page.locator("#btnPhoneOnly").click()
        assert page.locator("#appShell").evaluate("el => el.classList.contains('phone-only')") is True
        assert page.locator("#miniStrip").is_visible()
        page.locator("#btnExitPhoneOnly").click()
        assert page.locator("#appShell").evaluate("el => el.classList.contains('phone-only')") is False
        assert page.locator("#mainTopbar").is_visible()

        # 5. Phone-Style 3-Column App Icon Grid + async icon img + filter
        page.locator("#btnOpenAppsDrawer").click()
        page.wait_for_selector(".app-icon-grid .app-tile")
        assert page.locator(".app-tile").count() == 3
        page.wait_for_selector(".app-tile img")  # Zalo icon loaded asynchronously!
        page.locator("[data-app-filter='user']").click()
        assert page.locator(".app-tile").count() == 1
        page.locator(".app-tile").first.click()
        page.locator("#drawerApps [data-close-drawer]").click()

        # 6. Diagnostics & Health Panel (Battery, Touch Grid, Samsung *#0*#, Crash Force Stop)
        page.locator("#btnOpenDiagDrawer").click()
        page.wait_for_selector("#btnDiagPointerGrid")
        assert "35.3°C" in page.locator("#diagBody").inner_text()
        assert "Sweethome" in page.locator("#diagBody").inner_text()
        page.locator("#btnDiagPointerGrid").click()
        page.wait_for_function("() => document.getElementById('btnDiagPointerGrid').classList.contains('active')")
        page.locator("#btnDiagBatterySaver").click()
        page.locator("#btnDiagSamsungHw").click()
        page.locator(".crash-item button").first.click()
        page.locator("#drawerDiagnostics [data-close-drawer]").click()

        # 7. Demo 4 phones + Zoom levels
        page.locator("#selectDemoCount").select_option("4")
        page.wait_for_function("() => document.querySelectorAll('.phone-slot').length === 4")
        page.locator(".zoom-btn[data-zoom='50']").click()
        h50 = page.locator(".phone-slot-viewport").first.bounding_box()["height"]
        page.locator(".zoom-btn[data-zoom='125']").click()
        h125 = page.locator(".phone-slot-viewport").first.bounding_box()["height"]
        assert h125 > h50

        calls = page.evaluate("() => window.__calls")
        methods = [c[0] for c in calls]
        for expected in (
            "set_always_on_top",
            "set_display_power",
            "fetch_app_icons",
            "launch_package",
            "get_diagnostics",
            "set_pointer_location",
            "set_battery_saver",
            "launch_samsung_hw_test",
            "force_stop_package",
        ):
            assert expected in methods, f"Missing API call: {expected}"

        assert console_errors == [], f"Console errors: {console_errors}"
        assert page_errors == [], f"Page errors: {page_errors}"
        browser.close()
