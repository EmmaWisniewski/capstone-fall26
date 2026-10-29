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


def entry(key, role="in_scope"):
    year, chapter = key.split("-")
    return {"law_key": key, "acts_year": year, "chapter": chapter, "role": role}


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
    ]
    assert laws.laws_to_download(law_list) == ([(2023, "77"), (2020, "316"), (2019, "5")], [])
    assert laws.laws_to_download(law_list, law="2019-5") == ([(2019, "5")], [])
    assert laws.laws_to_download(law_list, law="2021-9")[1]  # excluded: reported, not fetched


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
