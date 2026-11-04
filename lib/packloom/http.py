from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import USER_AGENT


def request(url: str, timeout: int = 60, headers: dict | None = None) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})


def get_json(url: str, params: dict | None = None, retries: int = 3):
    """GET JSON. Lists are JSON-encoded in the query string, as Modrinth expects. 404 -> None."""
    if params:
        url += "?" + urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (list, dict)) else v
                                             for k, v in params.items()})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request(url), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"no answer from {url}")


def get_text(url: str) -> str:
    with urllib.request.urlopen(request(url), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def download(url: str, dest: Path, sha256: str | None = None, sha1: str | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(request(url), timeout=300) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if sha256 and file_hash(tmp, "sha256") != sha256.lower():
        tmp.unlink()
        raise RuntimeError(f"sha256 mismatch for {url}")
    if sha1 and file_hash(tmp, "sha1") != sha1.lower():
        tmp.unlink()
        raise RuntimeError(f"sha1 mismatch for {url}")
    tmp.replace(dest)
    return dest


def file_hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
