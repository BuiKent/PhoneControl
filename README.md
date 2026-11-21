# Phone Control v2.1

Lightweight Windows desktop control studio for **`scrcpy`** and **ADB** — built with Python + `pywebview` (native Edge WebView2, zero Electron overhead).

Combines a collapsible control sidebar on the left with an auto-arranging multi-phone mirroring workspace on the right in **one unified window**, supporting multiple Samsung / Android devices simultaneously over USB or Wi-Fi.

---

## Highlights (v2.1)

- **Unified Split Workspace & Phone-Only Mode**: Borderless `scrcpy` windows dock seamlessly into the right-hand workspace pane via Win32 owned-window synchronization (`window_host.py`). Collapse the left sidebar (`Ctrl+B`), pin **Always on Top** (`HWND_TOPMOST`), or switch to **Phone-Only Mode** (`Ctrl+Shift+H`) to hide all toolbars and keep only the phone screen plus a minimal 28px recovery strip.
- **Live Auto-Rotating Landscape Frame**: Polls Android `SurfaceOrientation` automatically and resizes docked `scrcpy` frames between portrait and landscape to match the phone (both when clicking Rotate and when apps/videos auto-rotate).
- **Unified Display Power Toggle (Off/On Anytime)**: Single toggle button with clear lit active state turns the physical phone display off/on mid-session via native `scrcpy` `Alt+O` / `Alt+Shift+O` (or headless fallback) without breaking mirroring.
- **Phone-Style 3-Column App Icon Grid**: Displays installed apps in a phone-like icon grid with cached icons (`icon_cache.py`), curated vector icons for built-in Samsung/Android system apps, All/User filter, and instant search.
- **Device Health & Diagnostics Panel**:
  - **Battery & Performance**: Real-time battery %, temperature (°C), voltage (V), battery health, RAM & internal storage usage bars, Battery Saver toggle, and background process cleanup (`am kill-all`).
  - **Screen & Touch Fault Testing**: One-click **Touch Grid (`pointer_location`)** overlay to spot dead touch zones / ghost touches, plus **Samsung Hardware Test (`*#0*#`)** launcher for RGB dead-pixel & sensor checks.
  - **Network & Crash/ANR Inspector**: Wi-Fi SSID, RSSI (dBm), link speed (Mbps), Internet ping latency, and recent app crashes/ANRs (`dumpsys dropbox`) with one-click **Force Stop**.
- **Parallel Multi-Phone Auto-Grid + 7 Zoom Levels + Demo Mode**: Mirror multiple phones simultaneously with automatic aspect-ratio-preserving grid layout, 7 Zoom presets (`Auto Fit`, `50%`, `75%`, `100%`, `125%`, `150%`, `Fill`), and built-in **Demo Grid (2 / 3 / 4 / 6 devices)**.
- **Touch Swipe Pad & Quick Launchers**: Directional swipe pad (Up/Down/Left/Right/Center Tap) with 3 stride levels calibrated from `wm size` (preferring `Override size`), white touch-dot toggle (`show_touches`), All Apps drawer button, and 4 quick launchers (**Phone**, **Camera**, **Messages**, **Gallery**).

---

## Requirements

- Windows 10 / 11 (WebView2 runtime preinstalled on Windows 11)
- Python 3.10+
- [`scrcpy`](https://github.com/Genymobile/scrcpy) v3+ / v5+ (bundles `adb.exe`):
  ```powershell
  winget install Genymobile.scrcpy
  ```

---

## Quick Start

```powershell
git clone https://github.com/BuiKent/PhoneControl.git
cd PhoneControl
pip install -r requirements.txt
python main.py
```

Double-click `launch.vbs` to start without a console window, or create a Desktop shortcut:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1
```

---

## Development & Tests

```powershell
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```

---

## License

MIT License — see [LICENSE](LICENSE).
