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
    assert [
        (r["line_item"], r["amount"], r["amount_struck"], r["veto_kind_inline"]) for r in items
    ] == [
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
        "370000000",
        "400000000",
        "reduced",
    )


def test_amount_without_dotted_leader_and_id_followed_by_a_space():
    items, unread = read(
        "<p>SECTION 2.</p><p>6121-2617 For municipal roads, which applies $4,400,000,000</p>"
    )
    assert not unread
    assert (items[0]["line_item"], items[0]["amount"]) == ("6121-2617", "4400000000")


# -- borrowing limits -----------------------------------------------------------

BORROW = (
    "<p>SECTION {n}. To meet the expenditures necessary in carrying out {covers}, the state "
    "treasurer shall, upon request of the governor, issue and sell bonds of the commonwealth in "
    "an amount to be specified by the governor from time to time but not exceeding, in the "
    "aggregate, ${limit}. All bonds issued by the commonwealth under this section shall be "
    "designated on their face, Test Act of 2099, and shall be issued for a maximum term of years, "
    "not exceeding 30 years, as the governor may recommend. All such bonds shall be payable not "
    "later than June 30, 2129. All interest and payments on account of principal on these "
    "obligations shall be payable from the General Fund.</p>"
)


def limits(body, section_1=SECTION_1):
    paras = paragraphs("2099-1", section_1 + body)
    items, _ = read_bonds.read_law("2099-1", paras)
    return read_bonds.read_limits("2099-1", read_bonds._sections(paras), items)


def test_limit_details_and_single_item_coverage():
    # 2021-15 §6: a limit for one item, not the whole section
    rows = limits(
        "<p>SECTION 2.</p><p>4000-2026 For the soldiers' home ...... $400</p>"
        "<p>4000-2027 For veterans' homes ...... $200</p>"
        + BORROW.format(n=6, covers="item 4000-2026 of section 2", limit="400")
    )
    assert rows == [
        {
            "law_key": "2099-1",
            "section": "6",
            "covers_sections": "2",
            "covers_items": "4000-2026",
            "authorized": "400",
            "items_total": "400",
            "federal_share": "",
            "federal_split": "none",
            "bond_name": "Test Act of 2099",
            "max_term_years": "30",
            "payable_by": "2129-06-30",
            "paying_fund": "General Fund",
            "available_through": "",
            "reader_version": read_bonds.READER_VERSION,
            "confidence": "high",
        }
    ]


def test_federal_split_identified_unknown_and_notes():
    rows = limits(
        "<p>SECTION 2.</p><p>6121-2114 For federally aided roads, based upon a prior or "
        "anticipated future commitment of federal funds ...... $500</p>"
        "<p>SECTION 2A.</p><p>1790-3014 For technology ...... $300</p>"
        "<p>SECTION 2C.</p><p>6121-2137 For bridges ...... $125</p>"
        + BORROW.format(n=3, covers="section 2", limit="100")
        + BORROW.format(n=4, covers="section 2A", limit="200")
        + "<p>SECTION 5. To meet a portion of the expenditures necessary in carrying out section "
        "2C, the state treasurer shall issue and sell federal grant anticipation notes of the "
        "commonwealth not exceeding, in the aggregate, $125; provided, that any pledge of federal "
        "highway construction funds may secure the notes.</p>"
    )
    assert [
        (r["section"], r["federal_split"], r["federal_share"], r["paying_fund"]) for r in rows
    ] == [
        ("3", "identified", "400", "General Fund"),  # items exceed the state-share limit
        ("4", "unknown", "", "General Fund"),  # items exceed the limit, nothing says why
        ("5", "unknown", "", "federal highway construction funds"),  # notes for "a portion"
    ]


def test_federal_reimbursement_expected_without_an_amount_is_unknown():
    # 2021-15 item 4000-2026: items equal the limit, but borrowing depends on federal
    # reimbursement of an unstated amount (Emma, 2026-11-06)
    rows = limits(
        "<p>SECTION 2.</p><p>4000-2026 For the soldiers' home; provided, that federal "
        "reimbursements received for the new facility shall be used to reduce the amount of bonds "
        "issued and sold by the commonwealth for this item ...... $400</p>"
        "<p>4000-2027 For veterans' homes; provided, that any federal reimbursement received by a "
        "state agency may be retained ...... $200</p>"
        + BORROW.format(n=6, covers="item 4000-2026 of section 2", limit="400")
        + BORROW.format(n=7, covers="item 4000-2027 of section 2", limit="200")
    )
    assert [(r["section"], r["federal_split"], r["federal_share"]) for r in rows] == [
        ("6", "unknown", ""),
        ("7", "none", ""),  # "may be retained" requires no federal money
    ]


def test_special_obligation_fund_and_spending_end_dates():
    section_1 = (
        "<p>SECTION 1. The sums set forth in sections 2 and 2A are hereby made available. The sums "
        "set forth in section 2 shall be made available until June 30, 2029. The sums set forth "
        "in section 2A shall be made available until June 30, 2034.</p>"
    )
    so = BORROW.format(n=4, covers="section 2A", limit="20").replace(
        "the General Fund", "the Commonwealth Transportation Fund"
    )
    rows = limits(
        "<p>SECTION 2.</p><p>7002-8066 For grants ...... $10</p>"
        "<p>SECTION 2A.</p><p>6720-2215 For rail ...... $20</p>"
        + BORROW.format(n=3, covers="section 2", limit="10")
        + so,
        section_1=section_1,
    )
    assert [(r["section"], r["paying_fund"], r["available_through"]) for r in rows] == [
        ("3", "General Fund", "2029-06-30"),
        ("4", "Commonwealth Transportation Fund", "2034-06-30"),
    ]


def test_capital_sections_inside_a_supplemental_are_read():
    # 2023-2 §3: capital items in a section numbered 3, covered by a borrowing section (Q25)
    paras = paragraphs(
        "2099-2",
        "<p>SECTION 1. The sums set forth in section 2 are hereby appropriated.</p>"
        "<p>SECTION 2.</p><p>1599-0001 Operating money ...... $5</p>"
        "<p>SECTION 3. To provide for a program of housing, the sums set forth in this section are "
        "hereby made available.</p><p>EXECUTIVE OFFICE OF ECONOMIC DEVELOPMENT</p>"
        "<p>7002-8041 For a capital grant program ...... $125</p>"
        + BORROW.format(n=77, covers="section 3", limit="125"),
    )
    items = read_bonds._outside_capital("2099-2", read_bonds._sections(paras))
    assert [
        (r["section"], r["line_item"], r["amount"], r["secretariat_header_raw"]) for r in items
    ] == [
        ("3", "7002-8041", "125", "EXECUTIVE OFFICE OF ECONOMIC DEVELOPMENT"),
    ]  # the operating item in §2 is read_items', not read here


def test_laws_to_read_skips_manual_and_excluded(root, tmp_path):
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
    # Other law types are read too, but only for capital sections outside §2 (Q25)
    assert [r["law_key"] for r in read_bonds.laws_to_read(ctx)] == ["2024-139", "2023-28"]


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


def test_samples_match_expected_bond_authorizations(sample_run, samples_dir):
    # 2024-139 and 2025-17's borrowing limits, in the §7.16 format
    path = sample_run.interim_dir / "bond_authorizations_raw.csv"
    assert schemas.validate_file("bond_authorizations_raw", path) == []
    _, rows = schemas.read_csv(path)
    header, expected = schemas.read_csv(samples_dir / "expected" / "bond_authorizations.csv")

    def key(r):
        return r["law_key"], int(r["section"])

    got = [{c: r[c] for c in header} for r in rows]
    assert sorted(got, key=key) == sorted(expected, key=key)
