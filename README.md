# Phone Control

Lightweight Windows desktop control panel for **`scrcpy`** and **ADB** — built with Python + `pywebview` (native Edge WebView2, zero Electron overhead).

Designed as a compact side-panel companion to `scrcpy` so you can auto-detect multiple Samsung / Android phones (USB & Wi-Fi), launch smooth 60fps mirroring, take instant full-resolution screenshots straight to your clipboard, and control hardware keys in one click.

---

## Features

- **Multi-Device Auto-Detection & Saved Profiles**: Polls ADB automatically, merges live USB/Wi-Fi devices with saved device profiles (stored in `%LOCALAPPDATA%\PhoneControl\config.json`), supports custom nicknames, battery & Android version readout.
- **Auto-Mirror on Plug-In**: Optional toggle to automatically open `scrcpy` whenever a previously saved device connects.
- **One-Click Screen Mirroring (`scrcpy` v5+)**:
  - 3 quality presets: **Lite** (`4M / 30fps / 1280px`), **Balanced** (`8M / 60fps`), **High** (`16M / 60fps`).
  - Quick toggles: *Turn phone screen off*, *Stay awake*, *Always on top*, *Audio forwarding*.
- **Full-Resolution Screenshot + Clipboard Copy**: Captures native PNG via `adb exec-out screencap -p`, validates the PNG header (detecting `FLAG_SECURE` screens), saves to `Pictures\PhoneControl`, and copies directly to the Windows Clipboard (`CF_DIB`) for instant `Ctrl+V` pasting.
- **Hardware & Navigation Remote Pad**: Back, Home, Recents, Volume −/+, Mute, Power, Notification Shade, Screen Rotation, Push File / Install APK, and Open Screenshots Folder.
- **Seamless Wi-Fi Mode**: Convert a USB-connected phone to wireless ADB (`tcpip 5555`) in one click, reconnect saved Wi-Fi IPs, or pair Android 11+ devices with pairing codes (`adb pair`).

---

## Requirements

- Windows 10 / 11 (with WebView2 runtime, preinstalled on Windows 11)
- Python 3.10+
- [`scrcpy`](https://github.com/Genymobile/scrcpy) (includes `adb.exe`):
  ```powershell
  winget install Genymobile.scrcpy
  ```

---

## Quick Start

1. Clone this repository and install Python dependencies:
   ```powershell
   git clone https://github.com/BuiKent/PhoneControl.git
   cd PhoneControl
   pip install -r requirements.txt
   ```
2. Launch the app:
   ```powershell
   python main.py
   ```
   Or double-click `launch.vbs` (launches cleanly without a console window).
3. *(Optional)* Create a Desktop shortcut (`Phone Control.lnk`):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1
   ```

---

## Connecting a New Android / Samsung Phone

1. On the phone, open **Settings → About phone → Software information** and tap **Build number** 7 times.
2. Open **Developer options** and enable **USB debugging**.
3. Plug in the USB cable and tap **Allow** (*Always allow from this computer*). The phone automatically appears in **Phone Control** and is saved for future sessions.
4. To go wireless, click **Chuyển sang Wi-Fi** (while plugged in) or click **+ Thêm máy** to pair via Android 11+ Wireless Debugging.

---

## Development & Tests

```powershell
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```

Test coverage includes:
- `tests/test_adb_service.py`: ADB device parsing, battery/IP extraction, `scrcpy` argument builder, PNG validation, keyevents, file push & APK install.
- `tests/test_device_store.py`: Atomic config persistence, device profiles, rename/delete, corrupt JSON recovery.
- `tests/test_api.py`: Live + saved device merging and single-shot auto-mirror behavior.
- `tests/test_ui_dom.py`: Real Chromium DOM interaction tests via Playwright (clicks, modals, toggles, zero console/page errors).

---

## License

MIT License — see [LICENSE](LICENSE).
