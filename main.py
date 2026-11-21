"""Entry point for PhoneControl desktop application."""

from __future__ import annotations

import sys
from pathlib import Path

import webview

from phone_control.api import PhoneControlAPI


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    ui_index = base_dir / "phone_control" / "ui" / "index.html"
    if not ui_index.exists():
        raise FileNotFoundError(f"UI not found: {ui_index}")

    api = PhoneControlAPI()
    window = webview.create_window(
        title="Phone Control — Điều khiển điện thoại",
        url=ui_index.as_uri(),
        js_api=api,
        width=460,
        height=820,
        min_size=(390, 640),
        background_color="#0F172A",
    )
    api.attach_window(window)
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
