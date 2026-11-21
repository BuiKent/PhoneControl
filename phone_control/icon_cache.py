"""App icon resolver with local disk cache and lightweight Play Store lookup."""

from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable


def default_icon_cache_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "PhoneControl" / "icon_cache"
    return Path.home() / ".phone_control" / "icon_cache"


def _fetch_play_store_icon_bytes(package: str, timeout: float = 3.5) -> bytes | None:
    """Fetch a 128px app icon from Google Play Store public metadata."""
    url = f"https://play.google.com/store/apps/details?id={package}&hl=en"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None

    match = re.search(r'property="og:image"\s+content="([^"]+)"', html) or re.search(
        r'content="([^"]+)"\s+property="og:image"', html
    )
    if not match:
        return None

    img_url = match.group(1)
    # Request a compact 128px square icon instead of full 512px/original
    img_url = re.sub(r"=s\d+[^\"&]*$", "=s128", img_url)
    if "googleusercontent.com" in img_url and "=s" not in img_url:
        img_url = f"{img_url}=s128"

    img_req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(img_req, timeout=timeout) as img_resp:
            data = img_resp.read()
            if len(data) < 100 or len(data) > 512_000:
                return None
            return data
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def _detect_mime(raw: bytes) -> str:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
        return "image/webp"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "image/png"


class AppIconCache:
    """Caches resolved Android app icons locally as base64 data URIs."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        fetcher: Callable[[str], bytes | None] = _fetch_play_store_icon_bytes,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else default_icon_cache_dir()
        self._fetcher = fetcher
        self._miss_file = self.cache_dir / "_missing.json"
        self._missing: set[str] = self._load_missing()

    def _load_missing(self) -> set[str]:
        if not self._miss_file.exists():
            return set()
        try:
            data = json.loads(self._miss_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return set(str(x) for x in data)
        except (OSError, json.JSONDecodeError):
            pass
        return set()

    def _save_missing(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._miss_file.write_text(json.dumps(sorted(self._missing)), encoding="utf-8")
        except OSError:
            pass

    def _icon_path(self, package: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", package)
        return self.cache_dir / f"{safe}.bin"

    def get_cached(self, package: str) -> str | None:
        path = self._icon_path(package)
        if not path.exists():
            return None
        try:
            raw = path.read_bytes()
            mime = _detect_mime(raw)
            return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        except OSError:
            return None

    def resolve_one(self, package: str, *, allow_network: bool = True) -> str | None:
        cached = self.get_cached(package)
        if cached:
            return cached
        if not allow_network or package in self._missing:
            return None

        raw = self._fetcher(package)
        if not raw:
            self._missing.add(package)
            return None

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._icon_path(package).write_bytes(raw)
        except OSError:
            pass
        mime = _detect_mime(raw)
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    def resolve_batch(
        self,
        packages: list[str],
        *,
        allow_network: bool = True,
        max_workers: int = 8,
    ) -> dict[str, str]:
        """Resolve icons for a list of packages in parallel; returns {package: data_uri}."""
        results: dict[str, str] = {}
        to_fetch: list[str] = []

        for pkg in packages:
            cached = self.get_cached(pkg)
            if cached:
                results[pkg] = cached
            elif allow_network and pkg not in self._missing:
                to_fetch.append(pkg)

        if to_fetch:
            before_missing = len(self._missing)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {pool.submit(self.resolve_one, pkg, allow_network=True): pkg for pkg in to_fetch}
                for fut in concurrent.futures.as_completed(future_map):
                    pkg = future_map[fut]
                    try:
                        uri = fut.result()
                        if uri:
                            results[pkg] = uri
                    except Exception:
                        pass
            if len(self._missing) != before_missing:
                self._save_missing()

        return results
