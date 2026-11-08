"""read_bonds: capital items in bond laws (DESIGN §7.3, §11.2)."""

import pytest

from ma_approps import read_bonds, schemas
from ma_approps.context import Context
from ma_approps.paragraphs import paragraphs

SECTION_1 = (
    "<p>SECTION 1. To provide for a program of capital improvements, the sums set forth in "
    "sections 2 and 2A are hereby made available.</p>"
)


def read(body):
    return read_bonds.read_law("2099-1", paragraphs("2099-1", SECTION_1 + body))


def test_pocket_vetoed_item_keeps_a_row_without_an_amount():
    # 2020-383 items 6720-2127 and 6921-2110: the whole item is crossed out
    items, unread = read(
        "<p>SECTION 2.</p><p>EXECUTIVE OFFICE OF TRANSPORTATION</p>"
        "<p>6121-2114.. For road projects ...... $1,000,000</p>"
        "<p><strong>Governor pocket vetoed the following item.</strong></p>"
        "<p><s>6720-2127 For early action capital work ...... $250,000,000</s></p>"
        "<p>SECTION 3. To meet the expenditures necessary in carrying out section 2, the state "
        "treasurer shall issue and sell bonds.</p>"
    )
    assert not unread
    assert [(r["line_item"], r["amount"], r["amount_struck"], r["veto_kind_inline"])
            for r in items] == [
        ("6121-2114", "1000000", "", "none"),
        ("6720-2127", "", "250000000", "disapproved"),
    ]
    assert items[1]["secretariat_header_raw"] == "EXECUTIVE OFFICE OF TRANSPORTATION"
    assert items[1]["reader_version"] == read_bonds.READER_VERSION


def test_reduced_item_keeps_its_final_amount():
    # 2020-383 item 6621-2117: $400,000,000 struck, $370,000,000 printed after it
    items, _ = read(
        "<p>SECTION 2.</p>"
        "<p><strong>Governor reduced the following item.</strong></p>"
        "<p>6621-2117.. For rail improvements ...... <s>$400,000,000</s> $370,000,000</p>"
    )
    assert (items[0]["amount"], items[0]["amount_struck"], items[0]["veto_kind_inline"]) == (
        "370000000", "400000000", "reduced",
    )


def test_amount_without_dotted_leader_and_id_followed_by_a_space():
    items, unread = read(
        "<p>SECTION 2.</p><p>6121-2617 For municipal roads, which applies $4,400,000,000</p>"
    )
    assert not unread
    assert (items[0]["line_item"], items[0]["amount"]) == ("6121-2617", "4400000000")


def test_laws_to_read_skips_manual_excluded_and_non_bond(root, tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    header = ",".join(schemas.columns("law_list"))
    rows = [
        "2024-139,2024,139,2024-11-20,,,,bond,in_scope,,,,auto,",
        "1993-52,1993,52,1993-05-21,,,,bond,reference_only,,,,manual,",
        "2021-9,2021,9,2021-04-01,,,,bond,excluded,,,,auto,",
        "2023-28,2023,28,2023-08-09,,,,gaa,in_scope,,,,auto,",
    ]
    (config / "law_list.csv").write_text("\n".join([header, *rows]) + "\n", "utf-8")
    (config / "settings.toml").write_bytes((root / "config" / "settings.toml").read_bytes())
    ctx = Context(root=tmp_path)
    assert [r["law_key"] for r in read_bonds.laws_to_read(ctx)] == ["2024-139"]


# -- samples ------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_run(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("read_bonds")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    assert read_bonds.run(ctx) == 0
    return ctx


def test_samples_match_schema(sample_run):
    path = sample_run.interim_dir / "bond_items_raw.csv"
    assert schemas.validate_file("bond_items_raw", path) == []


def test_samples_match_expected_bond_items(sample_run, samples_dir):
    # Emma's hand-checked expected output for 2024-139 and 2025-17 (16 items)
    _, rows = schemas.read_csv(sample_run.interim_dir / "bond_items_raw.csv")
    header, expected = schemas.read_csv(samples_dir / "expected" / "bond_items.csv")
    def key(r):
        return r["law_key"], int(r["para_start"])

    got = [{c: r[c] for c in header} for r in rows]
    assert sorted(got, key=key) == sorted(expected, key=key)
    assert {r["confidence"] for r in rows} == {"high"}


def test_samples_leave_nothing_unread(sample_run):
    _, unread = schemas.read_csv(sample_run.reports_dir / "unread_paragraphs_bonds.csv")
    assert unread == []
