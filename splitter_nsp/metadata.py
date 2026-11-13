"""Game name, icon and banner from api.nlib.cc, with an on-disk cache."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

API = "https://api.nlib.cc/nx"
_HEADERS = {"User-Agent": "SplitterNSP/1.0"}


def cache_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = base / "SplitterNSP"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status == 200:
                return r.read()
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return None


def fetch_metadata(title_id: str) -> Optional[dict]:
    path = cache_dir() / f"{title_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            pass
    data = _get(f"{API}/{title_id}")
    if not data:
        return None
    try:
        meta = json.loads(data)
    except ValueError:
        return None
    path.write_bytes(data)
    return meta


def fetch_image(title_id: str, kind: str) -> Optional[bytes]:
    """kind: 'icon' (512x512) or 'banner' (1280x720). Returns the JPEG bytes."""
    size = "512/512" if kind == "icon" else "1280/720"
    path = cache_dir() / f"{title_id}-{kind}.jpg"
    if path.exists():
        return path.read_bytes()
    data = _get(f"{API}/{title_id}/{kind}/{size}")
    if data:
        path.write_bytes(data)
    return data
