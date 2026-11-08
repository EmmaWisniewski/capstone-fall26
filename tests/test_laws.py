"""The `laws` stage's downloader, tested offline with a fake connection (no network)."""

import json
from dataclasses import dataclass, field

import pytest

from ma_approps import laws, schemas
from ma_approps.context import Context, load_settings

API = "https://malegislature.gov/api"
URL = f"{API}/SessionLaws/2023"
HTTP = {
    "user_agent": "ma-approps-test/0",
    "contact_email": "test@example.org",
    "min_interval_seconds": 1.0,
    "max_retries": 2,
    "backoff_base_seconds": 2.0,
    "timeout_seconds": 5,
}


@dataclass
class FakeResponse:
    status_code: int = 200
    content: bytes = b""
    headers: dict = field(default_factory=dict)


class FakeSession:
    """Answers GETs from ``routes`` (url -> response, or a list consumed one per call)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers))
        route = self.routes.get(url, FakeResponse(404))
        return route.pop(0) if isinstance(route, list) else route


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(routes, offline=False, **http):
    clock, session = FakeClock(), FakeSession(routes)
    client = laws.Client(
        HTTP | http, offline=offline, session=session, sleep=clock.sleep, clock=clock
    )
    return client, session, clock


def entry(key, role="in_scope", parse_strategy="auto"):
    year, chapter = key.split("-")
    return {
        "law_key": key,
        "acts_year": year,
        "chapter": chapter,
        "role": role,
        "parse_strategy": parse_strategy,
    }


@pytest.fixture
def year_list(samples_dir):
    """A fake /SessionLaws/2023 response: the 2023-77 sample plus a Resolve numbered 77."""
    law77 = json.loads((samples_dir / "sessionlaws" / "2023" / "77.json").read_text("utf-8"))
    resolve77 = {"Type": "Resolves", "ChapterNumber": "77", "Title": "A RESOLVE"}
    return FakeResponse(200, json.dumps([resolve77, law77]).encode("utf-8"))


# --- polite HTTP -----------------------------------------------------------------------------


def test_user_agent_names_the_contact():
    client, session, _ = make_client({URL: FakeResponse(200, b"[]")})
    assert client.get(URL) == b"[]"
    assert session.calls[0][1]["User-Agent"] == "ma-approps-test/0 (+test@example.org)"


def test_refuses_without_contact_email():
    client, session, _ = make_client({URL: FakeResponse(200, b"[]")}, contact_email="")
    with pytest.raises(laws.SettingsError):
        client.get(URL)
    assert session.calls == []


def test_waits_one_second_between_requests_to_the_same_site():
    other = "https://example.org/x"
    client, _, clock = make_client({URL: FakeResponse(200), other: FakeResponse(200)})
    client.get(URL)
    client.get(other)  # a different site doesn't wait
    assert clock.sleeps == []
    clock.now += 0.25
    client.get(URL)
    assert clock.sleeps == [pytest.approx(0.75)]


def test_retries_busy_server_with_growing_waits():
    busy = [FakeResponse(503), FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200)]
    client, session, clock = make_client({URL: busy}, min_interval_seconds=0)
    client.get(URL)
    assert len(session.calls) == 3
    assert clock.sleeps == [2.0, 7.0]  # 2s, then the server's Retry-After (7s) beats 4s


def test_gives_up_after_max_retries_and_never_retries_404():
    client, session, _ = make_client({URL: [FakeResponse(500)] * 5}, min_interval_seconds=0)
    with pytest.raises(laws.FetchError, match="after 2 retries"):
        client.get(URL)
    assert len(session.calls) == 3
    client, session, _ = make_client({})
    with pytest.raises(laws.FetchError) as e:
        client.get(URL)
    assert e.value.status == 404 and len(session.calls) == 1


# --- downloading -----------------------------------------------------------------------------


def test_downloads_every_role_except_excluded():
    law_list = [
        entry("2023-77"),
        entry("2020-316", "tbd"),
        entry("2021-9", "excluded"),
        entry("2019-5", "reference_only"),
        entry("1993-52", "reference_only", "manual"),  # older than the API; text kept by hand
    ]
    assert laws.laws_to_download(law_list) == ([(2023, "77"), (2020, "316"), (2019, "5")], [])
    assert laws.laws_to_download(law_list, law="2019-5") == ([(2019, "5")], [])
    assert laws.laws_to_download(law_list, law="2021-9")[1]  # excluded: reported, not fetched
    assert laws.laws_to_download(law_list, law="1993-52")[1]  # manual: reported, not fetched


def test_download_matches_sample_then_uses_cache(samples_dir, tmp_path, year_list):
    client, session, _ = make_client({URL: year_list})
    cache = laws.RawCache(tmp_path, now=lambda: "2026-10-28T12:00:00Z")
    assert laws.download_all([(2023, "77")], cache, client, API) == []
    cache.save_manifest()

    # The Act, not the Resolve with the same number, in the samples' exact format. Compare
    # without \r so the test also passes on Windows checkouts (core.autocrlf).
    sample = (samples_dir / "sessionlaws" / "2023" / "77.json").read_bytes()
    got = (tmp_path / laws.chapter_path(2023, "77")).read_bytes()
    assert got == sample.replace(b"\r\n", b"\n")
    assert (tmp_path / laws.year_list_path(2023)).is_file()

    header, rows = schemas.read_csv(tmp_path / "manifest.csv")
    assert schemas.validate_rows("raw_manifest", header, rows) == []
    paths = [r["path"] for r in rows]
    assert paths == sorted([laws.year_list_path(2023), laws.chapter_path(2023, "77")])

    # Second run: no requests, nothing rewritten, manifest unchanged.
    manifest = (tmp_path / "manifest.csv").read_bytes()
    cache2 = laws.RawCache(tmp_path, now=lambda: "2026-10-29T00:00:00Z")
    assert laws.download_all([(2023, "77")], cache2, client, API) == []
    cache2.save_manifest()
    assert len(session.calls) == 1
    assert cache2.written == []
    assert (tmp_path / "manifest.csv").read_bytes() == manifest


def test_offline_splits_chapter_from_cached_year_list(tmp_path, year_list):
    client, _, _ = make_client({URL: year_list})
    laws.download_all([(2023, "77")], laws.RawCache(tmp_path), client, API)
    (tmp_path / laws.chapter_path(2023, "77")).unlink()

    offline, session, _ = make_client({}, offline=True)
    assert laws.download_all([(2023, "77")], laws.RawCache(tmp_path), offline, API) == []
    assert (tmp_path / laws.chapter_path(2023, "77")).is_file()
    assert session.calls == []


def test_offline_lists_what_the_cache_is_missing(tmp_path):
    client, session, _ = make_client({}, offline=True)
    problems = laws.download_all([(2023, "77"), (2023, "28")], laws.RawCache(tmp_path), client, API)
    assert session.calls == []
    assert len(problems) == 2 and all("offline" in p for p in problems)


def test_one_failure_does_not_stop_the_rest(tmp_path, year_list):
    client, _, _ = make_client({URL: year_list})
    wanted = [(2023, "999"), (2023, "77")]
    problems = laws.download_all(wanted, laws.RawCache(tmp_path), client, API)
    assert len(problems) == 1 and problems[0].startswith("2023-999")
    assert (tmp_path / laws.chapter_path(2023, "77")).is_file()


def test_run_stops_without_contact_email(root, tmp_path, capsys):
    settings = load_settings(root / "config" / "settings.toml")
    settings["http"] = HTTP | {"contact_email": ""}
    ctx = Context(root=root, raw_dir=tmp_path, settings=settings, law="2023-77")
    assert laws.run(ctx) == 2
    assert "contact_email" in capsys.readouterr().out
    assert not (tmp_path / "manifest.csv").exists()


# --- discovery ------------------------------------------------------------------------------

SCOPE = {"approved_from": "2021-01-01", "approved_to": "2025-12-31"}
TODAY = laws.date(2026, 11, 7)


def act(chapter, body, title="AN ACT", approved="Mar 1 2023", resolve=False):
    return {
        "Type": "Resolves" if resolve else "Acts",
        "ChapterNumber": str(chapter),
        "Title": title,
        "ApprovedDate": approved,
        "ApprovalType": "Executive approval (signed)",
        "OriginBill": {"GeneralCourtNumber": 193, "BillNumber": "H4040"},
        "ChapterText": body,
    }


@pytest.mark.parametrize(
    ("body", "title", "signal"),
    [
        ("<p>SECTION 2.</p><p>1599-0001 For a reserve ...... $1,000</p>", "AN ACT", "line items"),
        (
            "<p>SECTION 1. The sum of $5,000 is hereby appropriated.</p>",
            "AN ACT",
            "hereby appropriated",
        ),
        (
            "<p>SECTION 3. Item 4513-1000 of section 2 of chapter 28 of the acts of 2023 is hereby "
            "amended by inserting the following words.</p>",
            "AN ACT REQUIRING EARLY INTERVENTION",  # 2022-83, the 2021-35 kind
            "amends a line item",
        ),
        (
            "<p>SECTION 4. The state treasurer shall issue and sell bonds.</p>",
            "AN ACT",
            "borrowing",
        ),
        (
            "<p>SECTION 1. Text.</p>",
            "AN ACT MAKING APPROPRIATIONS FOR THE FISCAL YEAR",
            "appropriation title",
        ),
    ],
)
def test_each_signal_flags_a_candidate(body, title, signal):
    assert signal in laws.signals(act(1, body, title))


@pytest.mark.parametrize(
    ("body", "title"),
    [
        # A land conveyance and a town charter: no appropriation, though the old signals matched
        (
            "<p>SECTION 1. The commissioner may convey a parcel.</p>",
            "AN ACT AUTHORIZING THE DIVISION OF CAPITAL ASSET MANAGEMENT AND MAINTENANCE TO CONVEY",
        ),
        (
            "<p>SECTION 6. Section 2-5 of said charter is hereby amended by striking out the "
            "figure "
            '"5" and inserting in place thereof the following figure:- 7.</p>',
            "AN ACT AMENDING THE CHARTER OF THE TOWN OF BOURNE",
        ),
    ],
)
def test_non_appropriation_acts_are_not_candidates(body, title):
    assert laws.signals(act(1, body, title)) == []


def test_discover_adds_new_candidates_only():
    records = {
        2023: [
            act(10, "<p>The sum of $5 is hereby appropriated.</p>"),  # new
            act(11, "<p>The sum of $5 is hereby appropriated.</p>"),  # listed: in_scope
            act(12, "<p>The sum of $5 is hereby appropriated.</p>"),  # listed: excluded
            act(13, "<p>The commissioner may convey a parcel.</p>"),  # no signal
            act(14, "<p>The sum of $5 is hereby appropriated.</p>", resolve=True),  # a Resolve
        ],
        2026: [act(55, "<p>The sum of $5 is hereby appropriated.</p>", approved="Apr 6 2026")],
    }
    law_list = [entry("2023-11"), entry("2023-12", "excluded")]
    rows = laws.discover(records, law_list, SCOPE, TODAY)
    assert [r["law_key"] for r in rows] == ["2023-10", "2026-55"]
    first, second = rows
    assert (first["role"], first["approved_date"], first["origin_bill"]) == (
        "tbd",
        "2023-03-01",
        "193/H4040",
    )
    assert first["include_reason"] == "Candidate: hereby appropriated"
    assert first["notes"] == "Found by discovery on 2026-11-07"
    assert laws.OUTSIDE_WINDOW_NOTE in second["notes"]
    # Running again with the new rows on the list adds nothing
    assert laws.discover(records, law_list + rows, SCOPE, TODAY) == []


def test_append_keeps_every_existing_byte(tmp_path):
    path = tmp_path / "law_list.csv"
    header = ",".join(schemas.columns("law_list"))
    before = f"{header}\r\n2023-11,2023,11,2023-03-01,,,,supplemental,in_scope,,,,auto,\r\n"
    path.write_bytes(before.encode("utf-8"))
    rows = laws.discover({2023: [act(10, "<p>hereby appropriated</p>")]}, [], SCOPE, TODAY)
    laws.append_to_law_list(path, rows)
    after = path.read_bytes()
    assert after.startswith(before.encode("utf-8"))
    _, read = schemas.read_csv(path)
    assert [r["law_key"] for r in read] == ["2023-11", "2023-10"]
    assert schemas.validate_file("law_list", path) == []


def test_run_discovers_from_the_cache_offline_but_not_for_one_law(root, tmp_path):
    raw = tmp_path / "raw"
    (raw / "sessionlaws" / "_lists").mkdir(parents=True)
    (raw / "sessionlaws" / "_lists" / "2023.json").write_text(
        json.dumps([act(10, "<p>The sum of $5 is hereby appropriated.</p>")]), "utf-8"
    )
    config = tmp_path / "config"
    config.mkdir()
    (config / "law_list.csv").write_text(",".join(schemas.columns("law_list")) + "\n", "utf-8")
    settings = load_settings(root / "config" / "settings.toml")
    settings["http"] = HTTP
    settings["scope"] = settings["scope"] | {"discover_years": [2023]}
    one = Context(root=tmp_path, raw_dir=raw, settings=settings, offline=True, law="2023-10")
    laws.run(one)
    assert schemas.read_csv(config / "law_list.csv")[1] == []  # --law: no discovery
    ctx = Context(root=tmp_path, raw_dir=raw, settings=settings, offline=True)
    laws.run(ctx)
    assert [r["law_key"] for r in schemas.read_csv(config / "law_list.csv")[1]] == ["2023-10"]


# --- amendment targets ----------------------------------------------------------------------


def amendment(law_key, section, target):
    return {"law_key": law_key, "section": section, "target_law_key": target}


def test_amendment_targets_come_only_from_in_scope_laws():
    law_list = [
        entry("2024-150"),
        entry("2019-41", "reference_only"),
        entry("2023-28"),
    ]
    amendments = [
        amendment("2024-150", "71", "2004-290"),
        amendment("2024-150", "72", "2004-290"),
        amendment("2024-150", "72", "2004-290"),  # two rows from one section: listed once
        amendment("2024-150", "80", "GL"),  # General Laws: never a law-list row
        amendment("2024-150", "90", "2023-28"),  # already listed
        amendment("2019-41", "27", "2018-154"),  # amended only by a reference-only law
        amendment("2023-28", "67", "2008-182"),
    ]
    assert laws.amendment_targets(amendments, law_list) == {
        "2004-290": ["2024-150 §71", "2024-150 §72"],
        "2008-182": ["2023-28 §67"],
    }


def test_discover_targets_adds_listed_targets_and_reports_missing_ones():
    targets = {
        "2004-290": [f"2024-150 §{n}" for n in range(71, 77)],
        "1993-77": ["2024-150 §61"],  # older than the API: not in any year list
    }
    records = {2004: [act(290, "<p>Housing bonds.</p>", approved="Aug 19 2004")]}
    rows, problems = laws.discover_targets(targets, records, SCOPE, TODAY)
    assert [r["law_key"] for r in rows] == ["2004-290"]
    row = rows[0]
    assert (row["role"], row["approved_date"]) == ("tbd", "2004-08-19")
    assert row["include_reason"] == (
        "Amendment target: amended by 2024-150 §71, 2024-150 §72, 2024-150 §73, 2024-150 §74 "
        "and 2 more"
    )
    assert row["notes"].startswith("Found by discovery (amendment target) on 2026-11-07")
    assert laws.OUTSIDE_WINDOW_NOTE in row["notes"]
    assert len(problems) == 1 and "1993-77" in problems[0] and "RUNBOOK" in problems[0]


def test_run_adds_amendment_targets_from_read_amendments_output(root, tmp_path, capsys):
    raw = tmp_path / "raw"
    (raw / "sessionlaws" / "_lists").mkdir(parents=True)
    (raw / "sessionlaws" / "_lists" / "2004.json").write_text(
        json.dumps([act(290, "<p>Housing bonds.</p>", approved="Aug 19 2004")]), "utf-8"
    )
    config = tmp_path / "config"
    config.mkdir()
    header = ",".join(schemas.columns("law_list"))
    (config / "law_list.csv").write_text(
        f"{header}\n2024-150,2024,150,2024-08-06,,,,bond,in_scope,,,,manual,\n", "utf-8"
    )
    settings = load_settings(root / "config" / "settings.toml")
    settings["http"] = HTTP
    settings["scope"] = settings["scope"] | {"discover_years": []}
    ctx = Context(
        root=tmp_path,
        raw_dir=raw,
        interim_dir=tmp_path / "interim",
        settings=settings,
        offline=True,
    )
    laws.run(ctx)  # no amendments file yet: skipped, with a hint
    assert "run read_amendments" in capsys.readouterr().out
    interim = tmp_path / "interim"
    interim.mkdir()
    cols = schemas.columns("amendments_raw")
    row = dict.fromkeys(cols, "") | {
        "law_key": "2024-150",
        "section": "71",
        "action_type": "purpose_change",
        "target_law_key": "2004-290",
    }
    (interim / "amendments_raw.csv").write_text(
        ",".join(cols) + "\n" + ",".join(row[c] for c in cols) + "\n", "utf-8"
    )
    laws.run(ctx)
    keys = [r["law_key"] for r in schemas.read_csv(config / "law_list.csv")[1]]
    assert keys == ["2024-150", "2004-290"]
    laws.run(ctx)  # a second run adds nothing
    assert [r["law_key"] for r in schemas.read_csv(config / "law_list.csv")[1]] == keys
