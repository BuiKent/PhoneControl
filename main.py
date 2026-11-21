"""Entry point for PhoneControl v2 desktop application."""

from __future__ import annotations

import sys
from pathlib import Path

import webview

from phone_control.api import PhoneControlAPI

APP_TITLE = "Phone Control — Điều khiển điện thoại"


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    ui_index = base_dir / "phone_control" / "ui" / "index.html"
    if not ui_index.exists():
        raise FileNotFoundError(f"UI not found: {ui_index}")

    api = PhoneControlAPI()
    window = webview.create_window(
        title=APP_TITLE,
        url=ui_index.as_uri(),
        js_api=api,
        width=1180,
        height=840,
        min_size=(640, 560),
        background_color="#0B1120",
    )
    api.attach_window(window, title=APP_TITLE)
    window.events.closed += api.shutdown
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
