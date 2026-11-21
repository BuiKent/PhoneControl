from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from phone_control.icon_cache import AppIconCache


def test_icon_cache_stores_fetches_and_remembers_missing(tmp_path: Path) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 120
    fetcher = MagicMock(side_effect=lambda pkg: png_bytes if pkg == "com.android.chrome" else None)

    cache = AppIconCache(cache_dir=tmp_path / "icons", fetcher=fetcher)
    res1 = cache.resolve_batch(["com.android.chrome", "com.sec.missing"])
    assert "com.android.chrome" in res1
    assert res1["com.android.chrome"].startswith("data:image/png;base64,")
    assert "com.sec.missing" not in res1
    assert fetcher.call_count == 2

    # Reload from disk: cached icon and missing record should avoid any network fetch
    fetcher2 = MagicMock(return_value=None)
    cache2 = AppIconCache(cache_dir=tmp_path / "icons", fetcher=fetcher2)
    res2 = cache2.resolve_batch(["com.android.chrome", "com.sec.missing"])
    assert res2["com.android.chrome"] == res1["com.android.chrome"]
    assert fetcher2.call_count == 0
