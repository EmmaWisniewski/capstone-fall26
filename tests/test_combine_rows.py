"""combine.supplemental_rows and combine.federal_grant_rows: read_items' items as funding-action
rows (DESIGN §7.7, §10; workstream B)."""

import pytest

from ma_approps import combine, read_items, schemas
from ma_approps.context import Context

URL = "https://malegislature.gov/Laws/SessionLaws/Acts/{acts_year}/Chapter{chapter}"


def law(key, law_type="supplemental", role="in_scope", approved="2023-12-04"):
    year, chapter = key.split("-")
    return {
        "law_key": key,
        "acts_year": year,
        "chapter": chapter,
        "law_type": law_type,
        "role": role,
        "approved_date": approved,
    }


def item(key, section, line_item, amount, fy="2023", **kw):
    row = dict.fromkeys(schemas.columns("items_raw"), "")
    row.update(
        law_key=key,
        section=section,
        line_item=line_item,
        amount=str(amount),
        fy_stated=fy,
        section_fund_default="General Fund",
        veto_kind_inline="none",
        para_start="5",
        para_end="5",
        reader_version="0.2.0",
        confidence="high",
    )
    row.update(kw)
    return row


def cthru(fy, line_item, original=0, funds=""):
    row = dict.fromkeys(schemas.columns("cthru_line_items"), "")
    row.update(
        fiscal_year=fy, line_item=line_item, original_enacted=str(original), fund_numbers=funds
    )
    return row


SUPP = law("2023-77")
GAA = law("2022-126", "gaa", approved="2022-07-28")


def supp(items, laws=(SUPP, GAA), cthru_rows=()):
    return combine.supplemental_rows(list(items), list(laws), list(cthru_rows), URL)


# -- supplemental rows ---------------------------------------------------------


@pytest.mark.parametrize(
    "section, section_type, action, kind, flags",
    [
        ("2", "approp_main", "INC", "delta", ""),
        ("2A", "approp_new", "NEW", "appropriation", ""),
        ("2B", "isf", "INC", "delta", "isf_chargeback"),
        ("2CI", "prior_approp", "PAC", "prior_appropriation_continued", ""),
        ("2CII", "prior_approp", "REAUTH", "prior_appropriation_continued", ""),
        ("2E", "trust_transfer", "NEW", "appropriation", "trust_transfer"),
        ("2Z", "approp_new", "NEW", "appropriation", "low_confidence_parse"),
    ],
)
def test_each_section_from_its_preamble(section, section_type, action, kind, flags):
    gaa_item = item("2022-126", "2", "0340-0400", 10)  # so §2's item is in FY2023's budget
    [row] = supp([item("2023-77", section, "0340-0400", 280000), gaa_item])
    assert (row["section_type"], row["funding_action"], row["amount_kind"]) == (
        section_type,
        action,
        kind,
    )
    assert row["flags"] == flags
    assert (row["amount"], row["amount_source"], row["veto_status"]) == (280000, "law_text", "none")


def test_common_fields():
    [row] = supp([item("2023-77", "2A", "1595-4514", 100000000, para_start="40")])
    assert row["target_law_key"] == "2023-77"  # a supplemental item is appropriated in its own law
    assert (row["event_date"], row["calendar_year"]) == ("2023-12-04", 2023)
    assert (row["fiscal_year"], row["fy_rule"]) == (2023, "stated")
    assert row["source_url"] == "https://malegislature.gov/Laws/SessionLaws/Acts/2023/Chapter77"
    assert (row["source_para_start"], row["section_fund_default"]) == ("40", "General Fund")
    assert "record_id" not in row and "counts_toward_total" not in row  # the shared core sets them


def test_a_section_2_item_not_in_that_years_budget_is_new_money():
    rows = supp(
        [
            item("2022-126", "2", "0340-0400", 10),  # FY2023 GAA has this item
            item("2023-77", "2", "0340-0400", 280000),
            item("2023-77", "2", "1599-9817", 5000),  # in neither the GAA nor CTHRU
            item("2023-77", "2", "4003-0100", 7000),  # CTHRU has it in FY2023
        ],
        cthru_rows=[cthru("2023", "4003-0100", original=100)],
    )
    assert [(r["line_item"], r["funding_action"], r["amount_kind"]) for r in rows] == [
        ("0340-0400", "INC", "delta"),
        ("1599-9817", "NEW", "appropriation"),
        ("4003-0100", "INC", "delta"),
    ]


def test_section_2_item_created_by_an_earlier_law_is_an_increase():
    # Emma's review of #46: 2022-268 §2 adds to 1599-0793, which 2022-42 §2A created in FY2022;
    # 2024-206 §2 adds to 1599-6073, which 2022-268 §2A created two years earlier
    laws = [
        law("2022-42", approved="2022-04-01"),
        law("2022-268", approved="2022-11-10"),
        law("2024-206", approved="2024-09-16"),
        GAA,
        law("2024-140", "gaa", approved="2024-07-29"),
    ]
    items = [
        item("2022-126", "2", "0340-0400", 10, fy="2022"),  # FY2022 and FY2024 budgets were read
        item("2024-140", "2", "0340-0400", 10, fy="2024"),
        item("2022-42", "2A", "1599-0793", 5, fy="2022"),
        item("2022-268", "2", "1599-0793", 6, fy="2022"),
        item("2022-268", "2A", "1599-6073", 7, fy="2022"),
        item("2024-206", "2", "1599-6073", 8, fy="2024"),
        item("2024-206", "2", "1599-7777", 9, fy="2024"),  # exists nowhere earlier
        item("2024-206", "2", "1599-8888", 9, fy="2024"),  # CTHRU has it in FY2023
    ]
    rows = supp(items, laws, cthru_rows=[cthru("2023", "1599-8888") | {"total_enacted": "50"}])
    assert [(r["law_key"], r["line_item"], r["funding_action"]) for r in rows] == [
        ("2022-42", "1599-0793", "NEW"),
        ("2022-268", "1599-0793", "INC"),
        ("2022-268", "1599-6073", "NEW"),
        ("2024-206", "1599-6073", "INC"),
        ("2024-206", "1599-7777", "NEW"),
        ("2024-206", "1599-8888", "INC"),
    ]


def test_section_2_stays_an_increase_when_that_years_budget_isnt_read():
    [row] = supp([item("2023-77", "2", "1599-9817", 5000, fy="2019")])
    assert row["funding_action"] == "INC"


def test_fund_printed_split_then_one_cthru_fund_then_the_section():
    rows = supp(
        [
            item("2023-77", "2A", "1599-0001", 1, fund_splits_raw="General Fund:60;Other Fund:40"),
            item("2023-77", "2A", "1599-0002", 1),  # CTHRU books it to one fund
            item("2023-77", "2A", "1599-0003", 1),  # CTHRU has two funds: use the section's
        ],
        cthru_rows=[
            cthru("2023", "1599-0002", funds="2005"),
            cthru("2023", "1599-0003", funds="0010;2005"),
        ],
    )
    assert [r.get("fund_splits_raw") for r in rows] == ["General Fund:60;Other Fund:40", "", ""]
    assert [r.get("fund_numbers", "") for r in rows] == ["", "2005", ""]


def test_vetoes_are_unverified():
    rows = supp(
        [
            item("2023-77", "2A", "1599-0001", 5, veto_kind_inline="wording_vetoed"),
            item(
                "2023-77", "2A", "1599-0002", "", amount_struck="9", veto_kind_inline="disapproved"
            ),
            item("2023-77", "2A", "1599-0003", 4, amount_struck="9", veto_kind_inline="reduced"),
        ]
    )
    assert [(r["amount"], r["amount_printed"], r["veto_status"]) for r in rows] == [
        (5, 5, "wording_vetoed"),
        (0, 9, "vetoed"),
        (4, 9, "reduced"),
    ]
    assert all(r["flags"] == "veto_unverified" for r in rows)


def test_available_through_and_multi_year():
    text = (
        "For shelters; provided, that funds shall not revert but shall be made available for the "
        "purposes of this item until June 30, 2025"
    )
    rows = supp(
        [
            item("2023-77", "2A", "1599-0001", 5, item_text=text),
            item("2023-77", "2A", "1599-0002", 5, item_text="available until June 30, 2023"),
        ]
    )
    assert [(r["available_through"], r["flags"]) for r in rows] == [
        ("2025-06-30", "multi_year"),
        ("", ""),  # within its own fiscal year
    ]


def test_only_in_scope_supplemental_surplus_and_other_laws():
    laws = [
        SUPP,
        law("2021-102", "surplus"),
        law("2020-316", "other"),
        law("2019-142", role="reference_only"),
        law("2025-17", "bond"),
        GAA,
    ]
    items = [
        item(k, "2A", "1599-0001", 1)
        for k in ("2023-77", "2021-102", "2020-316", "2019-142", "2025-17", "2022-126")
    ]
    assert [r["law_key"] for r in supp(items, laws)] == ["2023-77", "2021-102", "2020-316"]


# -- §2D federal grant rows ------------------------------------------------------


def test_federal_grant_rows():
    laws = [GAA, law("2019-41", "gaa", role="reference_only"), SUPP]
    items = [
        item(
            "2022-126", "2D", "0320-1710", 50000, section_fund_default="General Federal Grants Fund"
        ),
        item("2022-126", "2", "0340-0400", 10),  # Mario's annual-budget rows, not this piece
        item("2019-41", "2D", "0320-1710", 40000),  # reference-only
        item("2023-77", "2D", "0320-1710", 1),  # not a GAA
    ]
    [row] = combine.federal_grant_rows(items, laws, URL)
    assert (row["section_type"], row["funding_action"], row["amount_kind"]) == (
        "federal_grants",
        "ORIG",
        "appropriation",
    )
    assert (row["amount"], row["amount_source"], row["veto_status"]) == (
        50000,
        "law_text",
        "unknown",
    )
    assert (row["federal_share"], row["flags"]) == (1.0, "federal;veto_unverified")


def test_federal_grant_rows_never_count():
    [row] = combine.federal_grant_rows([item("2022-126", "2D", "0320-1710", 5)], [GAA], URL)
    rows, _, _ = combine.combine_rows({"§2D (B)": [row]}, [GAA], [])
    assert rows[0]["counts_toward_total"] == "false"


# -- the samples, through the shared core -----------------------------------------


@pytest.fixture(scope="module")
def sample_rows(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("combine_rows")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    assert read_items.run(ctx) == 0
    inputs = combine.load_inputs(ctx)
    pieces = {
        "supplemental rows (B)": combine._supplemental_builder(inputs, ctx.settings),
        "§2D federal grant rows (B)": combine._federal_grant_builder(inputs, ctx.settings),
    }
    rows, _, problems = combine.combine_rows(pieces, inputs["law_list"], inputs["funds"])
    return rows, problems


def test_samples_match_the_format(sample_rows, tmp_path):
    rows, problems = sample_rows
    assert problems == []
    path = tmp_path / "funding_actions.csv"
    combine._write(path, schemas.columns("funding_actions"), rows)
    assert schemas.validate_file("funding_actions", path) == []


def test_samples_rows(sample_rows):
    rows, _ = sample_rows
    by_law = {}
    for r in rows:
        by_law.setdefault(r["law_key"], []).append(r)
    # 2025-3: one supplemental increase, counted
    [r] = by_law["2025-3"]
    assert (r["record_id"], r["amount"], r["counts_toward_total"]) == (
        "2025-003-S2-1108-5200-INC-1",
        240000000,
        "true",
    )
    assert (r["fiscal_year"], r["fund_primary"]) == (2025, "General Fund")
    # 2023-77: §2 increases, §2A new money, §2CI/§2CII carried forward and not counted
    sections = {}
    for r in by_law["2023-77"]:
        sections.setdefault((r["section"], r["funding_action"], r["counts_toward_total"]), 0)
        sections[(r["section"], r["funding_action"], r["counts_toward_total"])] += 1
    assert sections == {
        ("2", "INC", "true"): 12,
        ("2A", "NEW", "true"): 14,
        ("2CI", "PAC", "false"): 57,
        ("2CII", "REAUTH", "false"): 6,
    }
    # The GAAs: only their §2D federal grants (the rest are Mario's annual-budget rows)
    assert {r["section"] for r in by_law["2023-28"] + by_law["2024-140"]} == {"2D"}
    assert (len(by_law["2023-28"]), len(by_law["2024-140"])) == (572, 540)
    assert all(
        r["counts_toward_total"] == "false" and r["veto_status"] == "unknown"
        for r in by_law["2023-28"]
    )
