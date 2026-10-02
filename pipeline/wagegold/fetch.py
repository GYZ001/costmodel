"""Download official data and keep an auditable raw snapshot of every response.

Every response body is written byte-for-byte under ``data/raw/`` and described in
``data/manifest.json`` (URL, request body, retrieval time, SHA-256, size).  Parsers
only ever read these snapshots, so any number on the site can be traced back to
the exact bytes a publisher served.

When a download fails, or the publisher answers with something that does not
look like the expected data, the previous snapshot is kept and flagged as
``stale`` with the error, instead of being overwritten by an error page.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import MANIFEST_PATH, RAW_DIR, REPO_ROOT, USER_AGENT

Check = Callable[[bytes], None]


class FetchError(RuntimeError):
    pass


@dataclass
class Snapshot:
    key: str
    url: str
    path: str
    retrieved_at: str
    sha256: str
    bytes: int
    content_type: str | None
    method: str = "GET"
    request_body: object | None = None
    status: str = "fresh"  # fresh | stale
    error: str | None = None
    attempted_at: str | None = None

    def read(self) -> bytes:
        return (REPO_ROOT / self.path).read_bytes()


@dataclass
class Fetcher:
    """Fetch-or-reuse raw snapshots.

    offline=True never touches the network: it serves the committed snapshots,
    which is how builds run in environments without access to the publishers.
    """

    offline: bool = False
    retries: int = 3
    timeout: int = 120
    manifest: dict[str, dict] = field(default_factory=dict)
    used: dict[str, Snapshot] = field(default_factory=dict)
    # Hosts that already failed at the network level in this run: further requests to
    # them fall back to committed snapshots at once instead of waiting out more timeouts.
    unreachable: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if MANIFEST_PATH.exists():
            self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def get(
        self,
        key: str,
        url: str,
        *,
        ext: str,
        json_body: object | None = None,
        record_body: object | None = None,
        headers: dict[str, str] | None = None,
        check: Check | None = None,
        timeout: int | None = None,
        retries: int | None = None,
    ) -> Snapshot:
        """Fetch ``url`` (POSTing ``json_body`` if given) unless offline.

        ``record_body`` is what the manifest stores as the request body; pass it
        when ``json_body`` carries a credential that must not be committed.
        """
        if key in self.used:
            return self.used[key]
        if self.offline:
            snap = self._previous(key)
            if snap is None:
                raise FetchError(f"{key}: offline and no committed snapshot")
            self.used[key] = snap
            return snap

        attempted_at = _now()
        try:
            host = urllib.parse.urlsplit(url).hostname or ""
            if host in self.unreachable:
                raise FetchError(f"{host} unreachable earlier in this run: {self.unreachable[host]}")
            body, ctype = self._download(url, json_body, headers, timeout, retries)
            if check is not None:
                check(body)
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the previous snapshot
            prev = self._previous(key)
            if prev is None:
                raise FetchError(f"{key}: {exc}") from exc
            prev.status = "stale"
            prev.error = f"{type(exc).__name__}: {exc}"[:500]
            prev.attempted_at = attempted_at
            self._record(prev)
            return prev

        rel = Path("data/raw") / f"{key}.{ext}"
        (REPO_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / rel).write_bytes(body)
        snap = Snapshot(
            key=key,
            url=url,
            path=rel.as_posix(),
            retrieved_at=attempted_at,
            sha256=hashlib.sha256(body).hexdigest(),
            bytes=len(body),
            content_type=ctype,
            method="POST" if json_body is not None else "GET",
            request_body=record_body if record_body is not None else json_body,
            attempted_at=attempted_at,
        )
        self._record(snap)
        return snap

    def committed(self, prefix: str) -> list[Snapshot]:
        """Previously committed snapshots whose key starts with ``prefix``."""
        out = []
        for key in sorted(self.manifest):
            if key.startswith(prefix):
                snap = self._previous(key)
                if snap is not None:
                    out.append(snap)
        return out

    def get_transient(self, url: str) -> bytes:
        """Download without snapshotting: only for discovery pages (e.g. release
        listings) whose content is not itself used as data."""
        if self.offline:
            raise FetchError(f"offline: cannot discover via {url}")
        body, _ = self._download(url, None, None, timeout=60, retries=2)
        return body

    def save_manifest(self) -> None:
        """Persist metadata for every snapshot used in this run (and keep the rest)."""
        merged = dict(self.manifest)
        for key, snap in self.used.items():
            merged[key] = asdict(snap)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # -- internals -----------------------------------------------------------------

    def _record(self, snap: Snapshot) -> None:
        self.used[snap.key] = snap

    def _previous(self, key: str) -> Snapshot | None:
        meta = self.manifest.get(key)
        if not meta or not (REPO_ROOT / meta["path"]).exists():
            return None
        return Snapshot(**meta)

    def _download(self, url: str, json_body: object | None, headers: dict[str, str] | None,
                  timeout: int | None = None, retries: int | None = None) -> tuple[bytes, str | None]:
        hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        hdrs.update(headers or {})
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode()
            hdrs["Content-Type"] = "application/json"
        last: Exception | None = None
        network_error = False
        for attempt in range(retries or self.retries):
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data else "GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                    return resp.read(), resp.headers.get("Content-Type")
            except urllib.error.HTTPError as exc:
                last, network_error = exc, False
                if exc.code < 500 and exc.code != 429:
                    break  # a 4xx other than rate limiting will not fix itself
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                last, network_error = exc, True
            time.sleep(2 * 2**attempt)
        if network_error:
            self.unreachable[urllib.parse.urlsplit(url).hostname or ""] = f"{type(last).__name__}: {last}"[:200]
        raise FetchError(f"download failed: {last}")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
