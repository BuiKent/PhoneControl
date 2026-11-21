from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


UI_INDEX = Path(__file__).resolve().parent.parent / "phone_control" / "ui" / "index.html"


def test_ui_v2_unified_workspace_real_dom_interactions() -> None:
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
                  show_touches: false,
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
                  show_touches: false,
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
                      devices: window.__state.devices.map(d => Object.assign({}, d, { mirroring: Boolean(window.__state.mirroring[d.serial]) }))
                    }
                  };
                },
                async scan_devices(trigger) {
                  window.__calls.push(["scan_devices", trigger]);
                  return {
                    ok: true,
                    data: {
                      devices: window.__state.devices.map(d => Object.assign({}, d, { mirroring: Boolean(window.__state.mirroring[d.serial]) })),
                      auto_mirrored: []
                    }
                  };
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
                async set_display_power(serial, on) {
                  window.__calls.push(["set_display_power", serial, on]);
                  return { ok: true, data: { serial, screen_on: on } };
                },
                async set_show_touches(serial, enabled) {
                  window.__calls.push(["set_show_touches", serial, enabled]);
                  const d = window.__state.devices.find(x => x.serial === serial);
                  if (d) d.show_touches = enabled;
                  return { ok: true, data: { serial, show_touches: enabled } };
                },
                async swipe(serial, direction, step) {
                  window.__calls.push(["swipe", serial, direction, step]);
                  return { ok: true, data: { serial, direction, step } };
                },
                async send_action(serial, action) {
                  window.__calls.push(["send_action", serial, action]);
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
                        { name: "Bộ sưu tập", package: "com.sec.android.gallery3d", system: true },
                        { name: "Chrome", package: "com.android.chrome", system: true },
                        { name: "Zalo", package: "com.zing.zalo", system: false }
                      ]
                    }
                  };
                },
                async launch_package(serial, pkg) {
                  window.__calls.push(["launch_package", serial, pkg]);
                  return { ok: true, data: { serial, package: pkg } };
                },
                async take_screenshot(serial, label) {
                  window.__calls.push(["take_screenshot", serial, label]);
                  return {
                    ok: true,
                    data: { path: "C:/Shots/shot1.png", filename: "shot1.png", copied_to_clipboard: true }
                  };
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
        assert page.locator(".device-item").count() == 2

        # 1. Mirror both phones in parallel inside the unified workspace
        page.locator("#btnMirrorAll").click()
        page.wait_for_function("() => document.querySelectorAll('.phone-slot').length === 2")
        assert page.locator(".phone-slot").count() == 2

        # 2. Live screen power off & on + white touch dot toggle
        page.locator("#btnScreenOffLive").click()
        page.locator("#btnScreenOnLive").click()
        page.locator("#btnToggleTouchDot").click()
        page.wait_for_function("() => document.getElementById('btnToggleTouchDot').getAttribute('aria-pressed') === 'true'")

        # 3. Touch Swipe Pad (up/down/left/right/center) + step size + App Drawer
        page.locator(".step-btn[data-step='long']").click()
        page.locator("[data-swipe='up']").click()
        page.locator("[data-swipe='down']").click()
        page.locator("[data-swipe='left']").click()
        page.locator("[data-swipe='right']").click()
        page.locator("[data-action='tap_center']").click()
        page.locator("[data-action='app_drawer']").click()

        # 4. Four quick app buttons (Phone, Camera, Messages, Gallery)
        for key in ("phone", "camera", "messages", "gallery"):
            page.locator(f"[data-app='{key}']").click()

        # 5. Inline Apps Drawer (search + launch package)
        page.locator("#btnOpenAppsDrawer").click()
        page.wait_for_selector(".app-row")
        page.locator("#inputSearchApps").fill("Zalo")
        assert page.locator(".app-row").count() == 1
        page.locator(".app-row").first.click()
        page.locator("#drawerApps [data-close-drawer]").click()
        assert page.locator("#drawerApps").is_hidden()

        # 6. Sidebar collapse & expand button
        page.locator("#btnToggleSidebar").click()
        page.wait_for_function("() => document.getElementById('controlSidebar').classList.contains('collapsed')")
        page.locator("#btnToggleSidebar").click()
        page.wait_for_function("() => !document.getElementById('controlSidebar').classList.contains('collapsed')")

        # 7. Multi-phone Demo mode (4 & 6 phones) + Zoom presets (fit, 50, 100, 150, fill)
        page.locator("#selectDemoCount").select_option("4")
        page.wait_for_function("() => document.querySelectorAll('.phone-slot').length === 4")
        h_fit = page.locator(".phone-slot-viewport").first.bounding_box()["height"]

        page.locator(".zoom-btn[data-zoom='50']").click()
        page.wait_for_function("() => document.querySelector('.zoom-btn.active').dataset.zoom === '50'")
        h_50 = page.locator(".phone-slot-viewport").first.bounding_box()["height"]

        page.locator(".zoom-btn[data-zoom='125']").click()
        page.wait_for_function("() => document.querySelector('.zoom-btn.active').dataset.zoom === '125'")
        h_125 = page.locator(".phone-slot-viewport").first.bounding_box()["height"]
        assert h_125 > h_50
        assert h_fit > 100

        page.locator("#selectDemoCount").select_option("6")
        page.wait_for_function("() => document.querySelectorAll('.phone-slot').length === 6")
        page.locator(".zoom-btn[data-zoom='fit']").click()
        page.locator("#selectDemoCount").select_option("0")

        # 8. Screenshot + Add Device Drawer + Narrow window smoke check (B10)
        page.locator("#btnScreenshot").click()
        page.wait_for_function("() => document.getElementById('statusMessage').textContent.includes('shot1.png')")

        page.locator("#btnOpenAddDrawer").click()
        assert page.locator("#drawerAddDevice").is_visible()
        page.locator("#inputWifiAddr").fill("192.168.1.88:5555")
        page.locator("#btnDoWifiConnect").click()
        page.wait_for_function("() => document.getElementById('drawerAddDevice').classList.contains('hidden')")

        page.set_viewport_size({"width": 760, "height": 640})
        page.wait_for_timeout(120)

        calls = page.evaluate("() => window.__calls")
        methods = [c[0] for c in calls]
        for expected in (
            "start_mirror",
            "sync_mirror_slots",
            "set_display_power",
            "set_show_touches",
            "swipe",
            "send_action",
            "launch_quick_app",
            "list_apps",
            "launch_package",
            "take_screenshot",
            "connect_wifi",
        ):
            assert expected in methods, f"Missing API call: {expected}"

        assert console_errors == [], f"Console errors: {console_errors}"
        assert page_errors == [], f"Page errors: {page_errors}"
        browser.close()
