# Phone Control v2

Lightweight Windows desktop control studio for **`scrcpy`** and **ADB** — built with Python + `pywebview` (native Edge WebView2, zero Electron overhead).

Combines a collapsible control sidebar on the left with an auto-arranging multi-phone mirroring workspace on the right in **one unified window**, supporting multiple Samsung / Android devices simultaneously over USB or Wi-Fi.

---

## What's New in v2.0

- **Unified Split-Screen Workspace**: Borderless `scrcpy` windows dock seamlessly into the right-hand workspace pane via Win32 owned-window synchronization (`window_host.py`). Collapse the left control sidebar anytime (`Ctrl+B`) to maximize screen space.
- **Parallel Multi-Phone Auto-Grid + 7 Zoom Levels**: Mirror 1, 2, 3, 4, or more phones simultaneously. Automatic aspect-ratio-preserving grid layout maximizes visible screen area on desktop, plus quick Zoom presets (**Auto Fit**, **50%**, **75%**, **100%**, **125%**, **150%**, **Fill**) and a built-in **Demo Grid (2 / 3 / 4 / 6 devices)** preview.
- **Live Physical Screen Off / On (Anytime)**: Turn off the physical phone display *mid-session* (even if accidentally woken) while keeping full PC mirroring & control via a lightweight headless `scrcpy` helper, plus one-click wake back on.
- **Touch Swipe Pad & White Touch Dot**: Directional swipe buttons (Up / Down / Left / Right / Center Tap) with adjustable swipe stride (*Short / Medium / Long*) for precise scrolling without trackpad overshoot, plus a lightweight native white touch-indicator toggle (`show_touches`).
- **All Apps Drawer & Quick Launchers**: Dedicated **All Apps** button (opens phone App Drawer), 4 one-click quick launchers (**Phone**, **Camera**, **Messages**, **Gallery**), and an inline searchable **Installed Apps** drawer (`scrcpy --list-apps`).

---

## Core Features

- **Multi-Device Auto-Detection & Saved Profiles**: Polls ADB automatically, merges live USB/Wi-Fi devices with saved profiles (`%LOCALAPPDATA%\PhoneControl\config.json`), supports custom nicknames, battery & Android version readout, and optional **Auto-Mirror on plug-in**.
- **Smooth 60fps Hardware Mirroring (`scrcpy` v5+)**: 3 quality presets (*Lite 30fps*, *Balanced 60fps*, *High 16M*), Stay Awake, Audio forwarding, and one-click USB-to-Wi-Fi conversion (`tcpip 5555`).
- **Full-Resolution Screenshot + Clipboard Copy**: Captures native PNG via `adb exec-out screencap -p`, validates PNG integrity (detecting `FLAG_SECURE`), saves to `Pictures\PhoneControl`, and copies directly to Windows Clipboard (`CF_DIB`) for instant `Ctrl+V` pasting.
- **Hardware Keys & File Transfer**: Back, Home, Recents, Volume −/+, Mute, Power, Notification Shade, Screen Rotation, Push File / Install APK, and Android 11+ Wireless Pairing (`adb pair`).

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

## Development & Verification

```powershell
pip install -r requirements-dev.txt
playwright install chromium
pytest -v
```

---

## License

MIT License — see [LICENSE](LICENSE).
