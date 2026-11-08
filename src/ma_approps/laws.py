"""Stage 1 `laws`: find spending laws and download their text (DESIGN §6, §7.1).

Owner: workstream A (Law list and bond bills).

**Done: downloading.** For every law in config/law_list.csv except `excluded` ones (`tbd`
candidates are downloaded so reviewers can read them) and `parse_strategy = manual` ones (text
the API doesn't have, such as laws older than the API, kept in ``review/sources/``), cache the
chapter's JSON in ``data/raw/sessionlaws/{acts_year}/{chapter}.json`` and record it in
``data/raw/manifest.csv`` (§7.15). Chapters are split out of one ``/api/SessionLaws/{year}`` request
per Acts volume, cached in ``data/raw/sessionlaws/_lists/{year}.json``. In that list the ``Year``
field is the approval year; the Acts volume is the year requested.

**Done: discovery** (runs first; skipped with ``--law``). For each year in ``[scope]
discover_years``, every Act not yet on the law list is checked for appropriation signals (see
``signals``) and, if any match, appended to config/law_list.csv with ``role = tbd`` for a person
to decide. Existing rows are never changed or re-added, so ``excluded`` decisions stick.

Cache first: a file already in ``data/raw/`` is never re-downloaded (delete it to refresh), and
unchanged content is never rewritten. Requests are throttled to ~1 per second with a User-Agent
naming the project and ``[http] contact_email``; without a contact email nothing is sent (§3.6).
With ``--offline`` nothing is downloaded and the stage lists what the cache is missing. The
sample laws in ``tests/samples/`` use the same layout and JSON format as the cache.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from ma_approps import schemas
from ma_approps.context import Context
from ma_approps.paragraphs import ITEM_START_RE, TRAILING_AMOUNT_RE, key, paragraphs

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
    rows = [
        r for r in law_list if r["role"] in DOWNLOAD_ROLES and r.get("parse_strategy") != "manual"
    ]
    if law:
        rows = [r for r in rows if r["law_key"] == law]
        if not rows:
            return [], [f"{law}: not in config/law_list.csv (or excluded, or entered by hand)"]
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


def year_records(cache: RawCache, client: Client, api_base: str, acts_year: int) -> list[dict]:
    """Every chapter of one Acts volume, from the cache or one request."""
    url = f"{api_base}/SessionLaws/{acts_year}"
    list_rel = year_list_path(acts_year)
    if cache.exists(list_rel):
        return cache.read_json(list_rel)
    records = json.loads(client.get(url))
    if not isinstance(records, list):
        raise ValueError(f"{url}: expected a JSON list, got {type(records).__name__}")
    cache.write(list_rel, serialize(records), url)
    return records


def download_law(
    cache: RawCache, client: Client, api_base: str, acts_year: int, chapter: str
) -> None:
    rel = chapter_path(acts_year, chapter)
    if cache.exists(rel):
        return
    records = year_records(cache, client, api_base, acts_year)
    url = f"{api_base}/SessionLaws/{acts_year}"
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


# ---------------------------------------------------------------------------
# Discovery (§6 stage 1)
# ---------------------------------------------------------------------------

# Full-text signals that a law may appropriate money. Tightened 2026-11-07 (Decision Log): on
# 2020-2026 they flag every law on the list plus 16 candidates, where "striking out the figure"
# and broad title words also flagged town charters and land conveyances.
TEXT_SIGNALS = {
    "hereby appropriated": re.compile(r"\bhereby appropriated\b", re.IGNORECASE),
    "amends a line item": re.compile(
        r"\bitems? \d{4}-\d{4}\b[^.]{0,400}?\bis hereby (?:further )?amended"
        r"|\bis hereby (?:further )?amended[^.]{0,200}?\bitems? \d{4}-\d{4}\b",
        re.IGNORECASE,
    ),
    "borrowing": re.compile(r"\bissue and sell (?:[\w-]+ ){0,4}?(?:bonds|notes)\b", re.IGNORECASE),
}
TITLE_SIGNAL = re.compile(
    r"MAKING APPROPRIATIONS|APPROPRIATIONS? FOR|FINANCING (?:THE|A|AN|IMPROVEMENTS)"
    r"|SUPPLEMENTARY|SUPPLEMENTING",
    re.IGNORECASE,
)
OUTSIDE_WINDOW_NOTE = (
    "approved outside the window: reference-only if an in-window fiscal year needs it"
)


def signals(record: Mapping[str, Any]) -> list[str]:
    """Which appropriation signals one Acts record shows (empty: not a candidate)."""
    texts = [key(p["text"]) for p in paragraphs("discovery", record.get("ChapterText") or "")]
    found = []
    if any(ITEM_START_RE.match(t) and TRAILING_AMOUNT_RE.search(t) for t in texts):
        found.append("line items")
    text = " ".join(texts)
    found += [name for name, rx in TEXT_SIGNALS.items() if rx.search(text)]
    if TITLE_SIGNAL.search(record.get("Title") or ""):
        found.append("appropriation title")
    return found


def _approved(record: Mapping[str, Any]) -> str:
    """``"Feb 28 2025"`` (sometimes with a time after it) -> ``2025-02-28``."""
    raw = " ".join(str(record.get("ApprovedDate") or "").split()[:3])
    return datetime.strptime(raw, "%b %d %Y").date().isoformat() if raw else ""


def _origin_bill(record: Mapping[str, Any]) -> str:
    bill = record.get("OriginBill") or {}
    court, number = bill.get("GeneralCourtNumber"), bill.get("BillNumber")
    return f"{court}/{number}" if court and number else ""


def discover(
    records_by_year: Mapping[int, list[Mapping[str, Any]]],
    law_list: list[Mapping[str, str]],
    scope: Mapping[str, Any],
    today: date,
) -> list[dict[str, str]]:
    """New law-list rows (``role = tbd``) for Acts not yet listed that show a signal."""
    listed = {r["law_key"] for r in law_list}
    window = (scope["approved_from"], scope["approved_to"])
    out = []
    for acts_year, records in sorted(records_by_year.items()):
        for r in records:
            if r.get("Type") != "Acts":
                continue
            law_key = schemas.law_key(acts_year, r["ChapterNumber"])
            if law_key in listed:
                continue
            found = signals(r)
            if not found:
                continue
            reason = "Candidate: " + ", ".join(found)
            out.append(_candidate(acts_year, r, reason, "discovery", window, today))
            listed.add(law_key)
    return out


def _candidate(
    acts_year: int,
    record: Mapping[str, Any],
    reason: str,
    found_by: str,
    window: tuple[str, str],
    today: date,
) -> dict[str, str]:
    """A ``role = tbd`` law-list row for one Acts record."""
    approved = _approved(record)
    notes = f"Found by {found_by} on {today.isoformat()}"
    if approved and not window[0] <= approved <= window[1]:
        notes += f"; {OUTSIDE_WINDOW_NOTE}"
    row = dict.fromkeys(schemas.columns("law_list"), "")
    row.update(
        law_key=schemas.law_key(acts_year, record["ChapterNumber"]),
        acts_year=str(acts_year),
        chapter=str(record["ChapterNumber"]),
        approved_date=approved,
        approval_type=record.get("ApprovalType") or "",
        api_title=record.get("Title") or "",
        role="tbd",
        include_reason=reason,
        origin_bill=_origin_bill(record),
        parse_strategy="auto",
        notes=notes,
    )
    return row


AMENDING_SECTIONS_SHOWN = 4


def amendment_targets(
    amendments: list[Mapping[str, str]], law_list: list[Mapping[str, str]]
) -> dict[str, list[str]]:
    """Laws that in-scope laws amend but the law list lacks, each with its amending sections
    ("2024-150 §71"), in source order. Laws amended only by reference-only laws are left out: they
    matter only for history the dataset doesn't report (Decision Log 2026-11-08)."""
    listed = {r["law_key"]: r["role"] for r in law_list}
    out: dict[str, list[str]] = {}
    for a in amendments:
        target = a.get("target_law_key") or ""
        if (
            not target
            or target == "GL"
            or target in listed
            or listed.get(a["law_key"]) != "in_scope"
        ):
            continue
        where = f"{a['law_key']} §{a['section']}"
        if where not in out.setdefault(target, []):
            out[target].append(where)
    return out


def discover_targets(
    targets: Mapping[str, list[str]],
    records_by_year: Mapping[int, list[Mapping[str, Any]]],
    scope: Mapping[str, Any],
    today: date,
) -> tuple[list[dict[str, str]], list[str]]:
    """``role = tbd`` rows for amendment targets, plus problems for targets not in the API."""
    window = (scope["approved_from"], scope["approved_to"])
    rows, problems = [], []
    for target, sections in sorted(targets.items()):
        acts_year, chapter = (int(x) for x in target.split("-"))
        found = [
            r
            for r in records_by_year.get(acts_year, [])
            if r.get("Type") == "Acts" and str(r.get("ChapterNumber")) == str(chapter)
        ]
        if not found:
            problems.append(
                f"amendment target {target} (amended by {sections[0]}) isn't in the Legislature's "
                "API: add it by hand (see docs/RUNBOOK.md, step 2)"
            )
            continue
        shown = ", ".join(sections[:AMENDING_SECTIONS_SHOWN])
        more = len(sections) - AMENDING_SECTIONS_SHOWN
        reason = f"Amendment target: amended by {shown}" + (f" and {more} more" if more > 0 else "")
        rows.append(
            _candidate(acts_year, found[0], reason, "discovery (amendment target)", window, today)
        )
    return rows, problems


def append_to_law_list(path: Path, rows: list[dict[str, str]]) -> None:
    """Add rows at the end of the law list, leaving every existing byte as it is."""
    if not rows:
        return
    data = path.read_bytes()
    newline = "\r\n" if b"\r\n" in data else "\n"
    if data and not data.endswith(newline.encode()):
        data += newline.encode()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=schemas.columns("law_list"), lineterminator=newline)
    w.writerows(rows)
    path.write_bytes(data + buf.getvalue().encode("utf-8"))


def run_discovery(ctx: Context, cache: RawCache, client: Client) -> tuple[int, list[str]]:
    """Append new candidates to the law list. Returns (how many, problems)."""
    path = ctx.config_dir / "law_list.csv"
    _, law_list = schemas.read_csv(path)
    records, problems = {}, []
    for acts_year in ctx.settings["scope"]["discover_years"]:
        try:
            records[acts_year] = year_records(
                cache, client, ctx.settings["sources"]["api_base"], acts_year
            )
        except (FetchError, ValueError) as e:
            problems.append(f"discovery, {acts_year}: {e}")
    new = discover(records, law_list, ctx.settings["scope"], date.today())

    # Amendment targets (§6 stage 1), from read_amendments' output of an earlier run
    amendments_path = ctx.interim_dir / "amendments_raw.csv"
    if amendments_path.exists():
        _, amendments = schemas.read_csv(amendments_path)
        targets = amendment_targets(amendments, law_list + new)
        for acts_year in sorted({int(t.split("-")[0]) for t in targets} - set(records)):
            try:
                records[acts_year] = year_records(
                    cache, client, ctx.settings["sources"]["api_base"], acts_year
                )
            except (FetchError, ValueError) as e:
                problems.append(f"amendment targets, {acts_year}: {e}")
        target_rows, target_problems = discover_targets(
            targets, records, ctx.settings["scope"], date.today()
        )
        new += target_rows
        problems += target_problems
    else:
        print("  no amendments_raw.csv yet: run read_amendments, then laws again for its targets")

    append_to_law_list(path, new)
    for r in new:
        print(f"  new candidate {r['law_key']} ({r['approved_date']}): {r['include_reason']}")
    return len(new), problems


def run(ctx: Context) -> int:
    cache = RawCache(ctx.raw_dir)
    client = Client(ctx.settings["http"], offline=ctx.offline)
    found, problems = 0, []
    try:
        if ctx.law is None:
            found, problems = run_discovery(ctx, cache, client)
        _, law_list = schemas.read_csv(ctx.config_dir / "law_list.csv")
        laws, more = laws_to_download(law_list, ctx.law)
        problems += more
        problems += download_all(laws, cache, client, ctx.settings["sources"]["api_base"])
    except SettingsError as e:
        print(f"  {e}")
        return 2
    finally:
        cache.save_manifest()
    for p in problems:
        print(f"  {p}")
    print(
        f"  new candidates: {found}; laws: {len(laws)}; requests: {client.requests_made}; "
        f"files written: {len(cache.written)}; problems: {len(problems)}"
    )
    if found:
        print("  review the new role=tbd rows in config/law_list.csv")
    return 1 if problems else 0
