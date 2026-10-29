"""Stage 1 `laws`: find spending laws and download their text (DESIGN §6, §7.1).

Owner: workstream A (Law list and bond bills).

**Done: downloading.** For every law in config/law_list.csv except `excluded` ones (`tbd`
candidates are downloaded so reviewers can read them), cache the chapter's JSON in
``data/raw/sessionlaws/{acts_year}/{chapter}.json`` and record it in ``data/raw/manifest.csv``
(§7.15). Chapters are split out of one ``/api/SessionLaws/{year}`` request per Acts volume, cached
in ``data/raw/sessionlaws/_lists/{year}.json``. In that list the ``Year`` field is the approval
year; the Acts volume is the year requested.

**Not yet: discovery.** Scanning each year's full text for appropriation language and appending
new candidates with role=tbd (never overwriting human decisions).

Cache first: a file already in ``data/raw/`` is never re-downloaded (delete it to refresh), and
unchanged content is never rewritten. Requests are throttled to ~1 per second with a User-Agent
naming the project and ``[http] contact_email``; without a contact email nothing is sent (§3.6).
With ``--offline`` nothing is downloaded and the stage lists what the cache is missing. The
sample laws in ``tests/samples/`` use the same layout and JSON format as the cache.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = True

DOWNLOAD_ROLES = ("in_scope", "reference_only", "tbd")
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def year_list_path(acts_year: int) -> str:
    return f"sessionlaws/_lists/{acts_year}.json"


def chapter_path(acts_year: int, chapter: str) -> str:
    return f"sessionlaws/{acts_year}/{chapter}.json"


# ---------------------------------------------------------------------------
# Polite HTTP (§3.6, §15)
# ---------------------------------------------------------------------------


class FetchError(RuntimeError):
    """A download failed for good (non-retryable status, retries used up, or offline)."""

    def __init__(self, url: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{url}: {message}")
        self.status = status


class SettingsError(Exception):
    """The settings don't allow any request (no contact email). Stops the whole run."""


class Client:
    """One request at a time: throttled per host, retried with backoff on 429/5xx.

    Tests pass a fake ``session`` and ``sleep``/``clock`` so nothing touches the network.
    """

    def __init__(
        self,
        http: Mapping[str, Any],
        *,
        offline: bool = False,
        session: Any = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http = http
        self.offline = offline
        self._session = session
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}  # host -> clock() of its last request
        self.requests_made = 0

    def user_agent(self) -> str:
        contact = (self.http.get("contact_email") or "").strip()
        if not contact:
            raise SettingsError(
                "set [http] contact_email in config/settings.toml before downloading (DESIGN §3.6)"
            )
        return f"{self.http['user_agent']} (+{contact})"

    def get(self, url: str) -> bytes:
        if self.offline:
            raise FetchError(url, "not in the cache (offline mode, nothing downloaded)")
        headers = {"User-Agent": self.user_agent()}
        session = self._session = self._session or requests.Session()
        host = urlsplit(url).netloc
        retries = int(self.http.get("max_retries", 5))
        attempt = 0
        while True:
            last = self._last.get(host)
            if last is not None:
                wait = float(self.http.get("min_interval_seconds", 1.0)) - (self._clock() - last)
                if wait > 0:
                    self._sleep(wait)
            self._last[host] = self._clock()
            self.requests_made += 1
            try:
                resp = session.get(
                    url, headers=headers, timeout=float(self.http.get("timeout_seconds", 60))
                )
            except requests.RequestException as e:
                status, retry_after, error = None, None, f"{type(e).__name__}: {e}"
            else:
                if resp.status_code == 200:
                    return resp.content
                status, error = resp.status_code, f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
                if status not in RETRY_STATUSES:
                    raise FetchError(url, error, status)
            attempt += 1
            if attempt > retries:
                raise FetchError(url, f"{error} after {retries} retries", status)
            delay = float(self.http.get("backoff_base_seconds", 2.0)) * 2 ** (attempt - 1)
            if retry_after and retry_after.isdigit():
                delay = max(delay, float(retry_after))
            self._sleep(delay)


# ---------------------------------------------------------------------------
# data/raw/ cache and manifest.csv (§7.15)
# ---------------------------------------------------------------------------


def serialize(obj: Any) -> bytes:
    """Sorted keys, one-space indent, trailing newline: the format of the committed samples."""
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class RawCache:
    def __init__(self, raw_dir: Path, now: Callable[[], str] = _utc_now) -> None:
        self.raw_dir = Path(raw_dir)
        self._now = now
        self.written: list[str] = []  # paths whose content changed this run
        self.manifest: dict[str, dict[str, str]] = {}
        if (self.raw_dir / "manifest.csv").exists():
            _, rows = schemas.read_csv(self.raw_dir / "manifest.csv")
            self.manifest = {r["path"]: r for r in rows}

    def exists(self, rel: str) -> bool:
        return (self.raw_dir / rel).is_file()

    def read_json(self, rel: str) -> Any:
        return json.loads((self.raw_dir / rel).read_bytes())

    def write(self, rel: str, data: bytes, source_url: str) -> None:
        """Store ``data`` at ``rel``; unchanged content is neither rewritten nor re-dated."""
        target = self.raw_dir / rel
        if target.is_file() and target.read_bytes() == data and rel in self.manifest:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        self.written.append(rel)
        self.manifest[rel] = {
            "path": rel,
            "source_url": source_url,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": str(len(data)),
            "fetched_at": self._now(),
        }

    def save_manifest(self) -> None:
        if not self.manifest:
            return
        cols = schemas.columns("raw_manifest")
        with open(self.raw_dir / "manifest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            for rel in sorted(self.manifest):
                w.writerow({c: self.manifest[rel].get(c, "") for c in cols})


# ---------------------------------------------------------------------------
# Downloading the listed laws
# ---------------------------------------------------------------------------


def laws_to_download(
    law_list: list[Mapping[str, str]], law: str | None = None
) -> tuple[list[tuple[int, str]], list[str]]:
    """``(acts_year, chapter)`` for each law to download, plus any problems."""
    rows = [r for r in law_list if r["role"] in DOWNLOAD_ROLES]
    if law:
        rows = [r for r in rows if r["law_key"] == law]
        if not rows:
            return [], [f"{law}: not in config/law_list.csv (or excluded)"]
    return [(int(r["acts_year"]), r["chapter"]) for r in rows], []


def select_chapter(records: list[Mapping[str, Any]], chapter: str) -> Mapping[str, Any]:
    """The one Acts record for ``chapter``; Resolves are numbered separately and skipped."""
    found = [
        r
        for r in records
        if r.get("Type") == "Acts" and str(r.get("ChapterNumber")) == str(chapter)
    ]
    if len(found) != 1:
        raise ValueError(f"expected 1 Acts chapter {chapter} in the year list, found {len(found)}")
    return found[0]


def download_law(
    cache: RawCache, client: Client, api_base: str, acts_year: int, chapter: str
) -> None:
    rel = chapter_path(acts_year, chapter)
    if cache.exists(rel):
        return
    url = f"{api_base}/SessionLaws/{acts_year}"
    list_rel = year_list_path(acts_year)
    if cache.exists(list_rel):
        records = cache.read_json(list_rel)
    else:
        records = json.loads(client.get(url))
        if not isinstance(records, list):
            raise ValueError(f"{url}: expected a JSON list, got {type(records).__name__}")
        cache.write(list_rel, serialize(records), url)
    cache.write(rel, serialize(select_chapter(records, chapter)), f"{url} (chapter {chapter})")


def download_all(
    laws: list[tuple[int, str]], cache: RawCache, client: Client, api_base: str
) -> list[str]:
    """Download each law, collecting failures instead of stopping. Returns the problems."""
    problems = []
    for acts_year, chapter in laws:
        try:
            download_law(cache, client, api_base, acts_year, chapter)
        except (FetchError, ValueError) as e:
            problems.append(f"{schemas.law_key(acts_year, chapter)}: {e}")
    return problems


def run(ctx: Context) -> int:
    _, law_list = schemas.read_csv(ctx.config_dir / "law_list.csv")
    laws, problems = laws_to_download(law_list, ctx.law)
    cache = RawCache(ctx.raw_dir)
    client = Client(ctx.settings["http"], offline=ctx.offline)
    try:
        problems += download_all(laws, cache, client, ctx.settings["sources"]["api_base"])
    except SettingsError as e:
        print(f"  {e}")
        return 2
    finally:
        cache.save_manifest()
    for p in problems:
        print(f"  {p}")
    print(
        f"  laws: {len(laws)}; requests: {client.requests_made}; files written: "
        f"{len(cache.written)}; problems: {len(problems)}"
    )
    print("  (discovery of new candidate laws is not implemented yet)")
    return 1 if problems else 0
