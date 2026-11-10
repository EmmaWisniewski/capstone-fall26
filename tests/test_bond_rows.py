"""combine.bond_rows: bond items as funding-action rows (DESIGN §7.7, §7.16; workstream A)."""

import csv

import pytest

from ma_approps import combine, read_bonds, schemas
from ma_approps.context import Context

URL = "https://malegislature.gov/Laws/SessionLaws/Acts/{acts_year}/Chapter{chapter}"


def law(key, role="in_scope", approved="2024-11-20"):
    year, chapter = key.split("-")
    return {
        "law_key": key,
        "acts_year": year,
        "chapter": chapter,
        "role": role,
        "approved_date": approved,
    }


def item(key, section, line_item, amount, **kw):
    row = dict.fromkeys(schemas.columns("bond_items_raw"), "")
    row.update(
        law_key=key,
        section=section,
        line_item=line_item,
        amount=str(amount),
        para_start="5",
        para_end="5",
        reader_version="0.2.0",
        confidence="high",
    )
    row.update(kw)
    return row


def limit(key, section, covers, authorized, total, split="none", share="", items="", through=""):
    return {
        "law_key": key,
        "section": section,
        "covers_sections": covers,
        "covers_items": items,
        "authorized": str(authorized),
        "items_total": str(total),
        "federal_split": split,
        "federal_share": str(share),
        "available_through": through,
    }


def test_a_bond_item_becomes_a_capital_authorization():
    rows = combine.bond_rows(
        [
            item(
                "2024-139",
                "2A",
                "1790-3014",
                750_000_000,
                agency_header_raw="Office of the Secretary",
            )
        ],
        [
            limit(
                "2024-139",
                "4",
                "2A;2B",
                1_055_000_000,
                1_455_000_000,
                "unknown",
                through="2030-12-31",
            )
        ],
        [law("2024-139")],
        URL,
    )
    assert len(rows) == 1
    r = rows[0]
    assert (r["record_id"], r["funding_action"], r["amount_kind"], r["section_type"]) == (
        "2024-139-S2A-1790-3014-CAP-1",
        "CAP",
        "bond_authorization",
        "capital",
    )
    assert (r["amount"], r["amount_source"], r["counts_toward_total"]) == (
        750_000_000,
        "law_text",
        "false",
    )
    # Approved November 20, 2024: fiscal year 2025, which runs July 2024 to June 2025
    assert (r["event_date"], r["calendar_year"], r["fiscal_year"], r["fy_rule"]) == (
        "2024-11-20",
        2024,
        2025,
        "enactment_fy",
    )
    assert r["available_through"] == "2030-12-31"
    assert r["federal_share"] == "" and r["flags"] == ""  # an unknown split subtracts nothing
    assert r["source_url"] == "https://malegislature.gov/Laws/SessionLaws/Acts/2024/Chapter139"
    assert list(r) == schemas.columns("funding_actions")


@pytest.mark.parametrize(("approved", "fy"), [("2021-06-30", 2021), ("2021-07-01", 2022)])
def test_fiscal_year_starts_on_july_1(approved, fy):
    assert combine.enactment_fy(approved) == fy


def test_pocket_vetoes_and_reference_only_laws_are_left_out():
    items = [
        item(
            "2020-383",
            "2G",
            "6720-2127",
            "",
            amount_struck="250000000",
            veto_kind_inline="disapproved",
        ),  # pocket-vetoed: never became law
        item("2020-151", "2", "1102-5700", 37_500_000),  # a reference-only bond law
        item(
            "2020-383",
            "2D",
            "6621-2117",
            370_000_000,
            amount_struck="400000000",
            veto_kind_inline="reduced",
        ),
    ]
    laws = [law("2020-383", approved="2021-01-15"), law("2020-151", "reference_only")]
    rows = combine.bond_rows(items, [], laws, URL)
    assert [r["line_item"] for r in rows] == ["6621-2117"]
    r = rows[0]
    assert (r["amount"], r["amount_printed"], r["veto_status"], r["flags"]) == (
        370_000_000,
        400_000_000,
        "reduced",
        "veto_unverified",
    )


def test_identified_federal_share_and_single_item_limits():
    # 2020-383 §32 covers only item 6121-2114: $4.4B of items, $880M limit, $3.52B federal
    items = [
        item("2020-383", "2", "6121-2114", 4_400_000_000),
        item("2020-383", "2", "6121-2117", 100_000_000),
    ]
    limits = [
        limit(
            "2020-383",
            "32",
            "2",
            880_000_000,
            4_400_000_000,
            "identified",
            3_520_000_000,
            items="6121-2114",
        ),
        limit("2020-383", "33", "2", 100_000_000, 100_000_000),
    ]
    rows = combine.bond_rows(items, limits, [law("2020-383", approved="2021-01-15")], URL)
    assert [(r["line_item"], r["federal_share"], r["flags"]) for r in rows] == [
        ("6121-2114", 0.8, "federal;federal_mixed"),
        ("6121-2117", "", ""),
    ]
    assert combine.limit_for(rows[0], limits)["section"] == "32"
    assert combine.limit_for(rows[1], limits)["section"] == "33"
    assert combine.capital_total(rows) == 880_000_000 + 100_000_000


def test_record_ids_count_repeats_in_source_order():
    items = [item("2025-17", "2A", "6121-2617", 5), item("2025-17", "2A", "6121-2617", 7)]
    rows = combine.bond_rows(items, [], [law("2025-17", approved="2025-06-30")], URL)
    assert [r["record_id"] for r in rows] == [
        "2025-017-S2A-6121-2617-CAP-1",
        "2025-017-S2A-6121-2617-CAP-2",
    ]


# -- samples ------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_rows(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("bond_rows")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    assert read_bonds.run(ctx) == 0
    items = schemas.read_csv(ctx.interim_dir / "bond_items_raw.csv")[1]
    limits = schemas.read_csv(ctx.interim_dir / "bond_authorizations_raw.csv")[1]
    laws = schemas.read_csv(root / "config" / "law_list.csv")[1]
    rows = combine.bond_rows(items, limits, laws, ctx.settings["sources"]["session_law_url"])
    path = out / "funding_actions.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.columns("funding_actions"), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows, path


def test_samples_give_one_row_per_expected_item(sample_rows, samples_dir):
    rows, _ = sample_rows
    _, expected = schemas.read_csv(samples_dir / "expected" / "bond_items.csv")
    assert sorted(
        (r["law_key"], r["section"], r["line_item"], str(r["amount"])) for r in rows
    ) == sorted((e["law_key"], e["section"], e["line_item"], e["amount"]) for e in expected)


def test_samples_pass_the_funding_actions_format(sample_rows):
    _, path = sample_rows
    assert schemas.validate_file("funding_actions", path) == []


def test_samples_capital_total(sample_rows):
    rows, _ = sample_rows
    # 2024-139 ($1,656,989,000) + 2025-17 ($1,185,000,000); neither has an identified federal share
    assert combine.capital_total(rows) == 1_656_989_000 + 1_185_000_000
