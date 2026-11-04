"""read_amendments (DESIGN §11.3) on the offline sample laws: 2023-77, 2021-35, 2023-15 and
2023-28."""

import json
from pathlib import Path

import pytest

from ma_approps import paragraphs, read_amendments, schemas
from ma_approps.context import Context

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def output(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("read_amendments")
    ctx = Context(
        root=ROOT,
        raw_dir=ROOT / "tests" / "samples",
        interim_dir=tmp / "interim",
        reports_dir=tmp / "reports",
        offline=True,
    )
    assert read_amendments.run(ctx) == 0
    return ctx


@pytest.fixture(scope="module")
def rows(output):
    _, rows = schemas.read_csv(output.interim_dir / "amendments_raw.csv")
    return {(r["law_key"], r["section"], r["target_item"]): r for r in rows}


def _pick(row, *fields):
    return {f: row[f] for f in fields}


def test_output_matches_schema(output):
    assert schemas.validate_file("amendments_raw", output.interim_dir / "amendments_raw.csv") == []


def test_ex004_figure_change(rows):
    # 2023-77 §178: "Said Item 2330-0100 of said section 2 of said chapter 28 ... $9,310,231 ...
    # $9,660,231" → +350,000 against the FY2024 GAA (EX-004)
    row = rows[("2023-77", "178", "2330-0100")]
    assert _pick(
        row, "action_type", "target_law_key", "target_section", "old_figure", "new_figure"
    ) == {
        "action_type": "figure_change",
        "target_law_key": "2023-28",
        "target_section": "2",
        "old_figure": "9310231",
        "new_figure": "9660231",
    }
    assert row["confidence"] == "high"


def test_date_extension_and_said_resolution(rows):
    # §41 names 2019 ch. 142 in full; §42 says only "said item … of said section 2A of said
    # chapter 142"
    for section in ("41", "42"):
        row = rows[("2023-77", section, "7008-1117")]
        assert _pick(
            row, "action_type", "target_law_key", "target_section", "old_date", "new_date"
        ) == {
            "action_type": "date_extend",
            "target_law_key": "2019-142",
            "target_section": "2A",
            "old_date": "2023",
            "new_date": "2024",
        }


def test_said_chapter_uses_earlier_mention(rows):
    # §47: "Item 8000-0313 of said section 2 of said chapter 24" → chapter 24 of the acts of 2021
    row = rows[("2023-77", "47", "8000-0313")]
    assert (row["target_law_key"], row["old_date"], row["new_date"]) == (
        "2021-24",
        "2023-06-30",
        "2024-06-30",
    )


def test_text_only_change(rows):
    # §179 inserts proviso words into 4000-0300 (DESIGN §11.3: text-only change)
    row = rows[("2023-77", "179", "4000-0300")]
    assert (row["action_type"], row["target_law_key"], row["new_figure"]) == (
        "text_insert",
        "2023-28",
        "",
    )


def test_item_insert(rows):
    # §176: "Said section 2 of said chapter 28 is hereby further amended by inserting after item
    # 1599-7114 the following item:- 1599-4448 … $312,162,361"
    row = rows[("2023-77", "176", "1599-4448")]
    assert _pick(row, "action_type", "target_law_key", "target_section", "new_figure") == {
        "action_type": "item_insert",
        "target_law_key": "2023-28",
        "target_section": "2",
        "new_figure": "312162361",
    }


def test_both_times_figure_is_high_confidence(rows):
    # §81 changes "$320,000" "both times it appears" in 3000-7040, a retained-revenue item whose
    # ceiling and amount are both $320,000 in the FY2023 GAA: the item's total, not an earmark (Q21)
    row = rows[("2023-77", "81", "3000-7040")]
    assert (row["old_figure"], row["new_figure"], row["confidence"]) == ("320000", "520000", "high")


def test_figure_in_one_line_stays_low_confidence():
    # "in line 7" may be an earmark in the item's text rather than its total
    found = read_amendments._amendment_actions(
        ' by striking out, in line 7, the figure "$100,000" and inserting in place thereof the'
        " following figure:- $200,000.",
        ["1234-5678"],
        [],
    )
    assert [a["confidence"] for a in found] == ["low"]


def test_month_and_day_date_change(rows):
    # §49: "July 1" → "November 30" in 4000-0300 of 2021 ch. 24. The year (2023) is in the item's
    # own text, so the dates are recorded as written.
    row = rows[("2023-77", "49", "4000-0300")]
    assert _pick(row, "action_type", "target_law_key", "old_date", "new_date") == {
        "action_type": "date_extend",
        "target_law_key": "2021-24",
        "old_date": "July 1",
        "new_date": "November 30",
    }


def test_unexpended_balances_not_reverting(rows, output):
    # 2023-77 §214: balances in 4000-0700 and 4000-1426 of 2022 ch. 126 "shall not revert … until
    # September 1, 2023" works as a date extension for each item
    for item in ("4000-0700", "4000-1426"):
        row = rows[("2023-77", "214", item)]
        assert _pick(row, "action_type", "target_law_key", "target_section", "new_date") == {
            "action_type": "date_extend",
            "target_law_key": "2022-126",
            "target_section": "2",
            "new_date": "2023-09-01",
        }
    _, unread = schemas.read_csv(output.reports_dir / "unread_sections.csv")
    assert ("2023-77", "214") not in {(r["law_key"], r["section"]) for r in unread}


def test_transfer_from_fund_to_fund_with_a_bound(rows):
    # 2023-28 §95: "transfer from the General Fund to the Health Safety Net Trust Fund … the
    # greater of $45,000,000 or 1/12 of …": $45,000,000 is only a lower bound, so low confidence
    row = rows[("2023-28", "95", "")]
    assert _pick(row, "action_type", "amount", "fund_raw", "confidence") == {
        "action_type": "transfer",
        "amount": "45000000",
        "fund_raw": "General Fund",
        "confidence": "low",
    }


def test_amendment_of_an_amendment(rows):
    # 2023-77 §56 replaces section 67 of 2021 ch. 102, which amends item 8200-0200 of 2021 ch. 24
    # ("… available until June 30, 2024"); read as low confidence for a human to confirm
    row = rows[("2023-77", "56", "8200-0200")]
    assert _pick(row, "action_type", "target_law_key", "new_date", "confidence") == {
        "action_type": "date_extend",
        "target_law_key": "2021-24",
        "new_date": "2024-06-30",
        "confidence": "low",
    }


def test_transfer_source_item_and_funds(rows):
    # 2023-28 §93: "from the prescription advantage program in line-item 9110-1455 … and the
    # Health Safety Net Trust Fund"; §100 names a federal fund in lowercase
    row = rows[("2023-28", "93", "")]
    assert (row["from_item"], row["fund_raw"]) == ("9110-1455", "Health Safety Net Trust Fund")
    assert rows[("2023-28", "100", "")]["fund_raw"] == (
        "federal COVID-19 response fund; Transitional Escrow Fund"
    )


def test_section_2_heading_in_any_case():
    # The FY2022 GAA (2021-24) prints its Section 2 heading as "Section 2", with no period (issue
    # #12). Its items belong to read_items, so their text must not be read as part of §1B.
    html = (
        "<p>SECTION 1B. The comptroller shall transfer $5,000 from the General Fund to the Arts"
        " Fund.</p>"
        "<p>Section 2</p>"
        "<p>1599-0001 For a reserve; provided, that the comptroller shall transfer $79,000,000 from"
        " the General Fund to the Example Trust Fund.................... $1,000</p>"
        "<p>SECTION 3. Notwithstanding any general or special law to the contrary, this section"
        " takes effect upon passage.</p>"
    )
    rows, unread = read_amendments.read_law("2021-24", "gaa", html)
    assert [(r["section"], r["amount"]) for r in rows] == [("1B", 5000)]
    assert unread == []


def test_inserted_item_needs_no_space_after_its_number():
    # Tierney's heads-up: 2024-140 prints "4125-0122vFor", with no space after the item number
    items = read_amendments._inserted_items(["4125-0122vFor the operation ........... $100,000"])
    assert items == {"4125-0122": 100000}


def test_item_replaced_by_a_renumbered_item():
    # 2022-268 §228 strikes item 4003-0100 and inserts 4003-0122 ($10,000,000) in its place:
    # the old item is struck and the new one inserted, so the $10,000,000 isn't lost
    html = (
        "<p>SECTION 228. Section 2 of chapter 42 of the acts of 2022 is hereby amended by striking"
        " out item 4003-0100 and inserting in place thereof the following item:-</p>"
        "<p>4003-0122 ............................................. $10,000,000</p>"
    )
    rows, _ = read_amendments.read_law("2022-268", "supplemental", html)
    found = [(r["action_type"], r["target_item"], r.get("new_figure")) for r in rows]
    assert found == [("item_strike", "4003-0100", None), ("item_insert", "4003-0122", 10000000)]
    assert {r["target_law_key"] for r in rows} == {"2022-42"}


def test_whole_item_replacement(rows):
    # 2021-35 §1 replaces item 8100-1014 of 2019 ch. 5 §2A; the new item is $8,000,000
    row = rows[("2021-35", "1", "8100-1014")]
    assert _pick(row, "action_type", "target_law_key", "target_section", "new_figure") == {
        "action_type": "item_replace",
        "target_law_key": "2019-5",
        "target_section": "2A",
        "new_figure": "8000000",
    }


def test_interim_lump_sum(rows):
    # 2023-15 §1: "the amount of $6,660,000,000 is hereby appropriated for the fiscal year ending
    # June 30, 2024" is the law's only row
    found = [r for (law, _, _), r in rows.items() if law == "2023-15"]
    assert len(found) == 1
    assert _pick(found[0], "section", "action_type", "amount", "target_item") == {
        "section": "1",
        "action_type": "direct_appropriation",
        "amount": "6660000000",
        "target_item": "",
    }


def test_appropriation_sections_are_left_to_read_items(rows):
    # 2023-77 §2 supplements 0340-0400; that is read_items' job, not an amendment
    assert not any(law == "2023-77" and section == "2" for law, section, _ in rows)


def test_vetoed_section_is_low_confidence_and_listed(rows, output):
    # 2023-28 §100 is struck through under "The Governor disapproved of the following section".
    # It is still read, but flagged so a human checks whether the veto was overridden (§11.4).
    row = rows[("2023-28", "100", "")]
    assert _pick(row, "action_type", "amount", "confidence") == {
        "action_type": "transfer",
        "amount": "205000000",
        "confidence": "low",
    }
    _, unread = schemas.read_csv(output.reports_dir / "unread_sections.csv")
    reasons = {(r["law_key"], r["section"]): r["reason"] for r in unread}
    assert reasons[("2023-28", "100")].startswith("looks vetoed")


def test_veto_note_belongs_to_the_following_section(samples_dir):
    # The note is printed at the end of §99 but is about §100
    record = json.loads((samples_dir / "sessionlaws" / "2023" / "28.json").read_text("utf-8"))
    paras = paragraphs.paragraphs("2023-28", record["ChapterText"])
    sections = {s["section"]: s for s in read_amendments._sections(paras)}
    assert not any("Governor disapproved" in t for t in sections["99"]["texts"])
    assert (sections["99"]["vetoed"], sections["100"]["vetoed"]) == (False, True)


def test_unread_sections_have_explanation_column(output):
    header, unread = schemas.read_csv(output.reports_dir / "unread_sections.csv")
    assert header == list(read_amendments.UNREAD_COLUMNS)
    assert ("2023-28", "99") in {(r["law_key"], r["section"]) for r in unread}


def test_law_filter(root, samples_dir, tmp_path):
    ctx = Context(
        root=root,
        raw_dir=samples_dir,
        interim_dir=tmp_path / "interim",
        reports_dir=tmp_path / "reports",
        law="2021-35",
        offline=True,
    )
    assert read_amendments.run(ctx) == 0
    _, rows = schemas.read_csv(tmp_path / "interim" / "amendments_raw.csv")
    assert [r["law_key"] for r in rows] == ["2021-35"]
