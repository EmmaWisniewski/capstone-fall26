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


def test_transfer_destination_after_to():
    # 2024-88 §25 (shortened): the destination is the first item after "to", however it is named
    html = (
        "<p>SECTION 25. Notwithstanding any general or special law to the contrary, the"
        " comptroller may transfer not more than $175,000,000 from the Transitional Escrow Fund"
        " established by section 16 of chapter 76 of the acts of 2021, to the reserve established"
        " in item 1599-0514 of section 2A of chapter 77 of the acts of 2023 for the purposes of"
        " item 7004-0101 of section 2 of chapter 28 of the acts of 2023.</p>"
    )
    rows, _ = read_amendments.read_law("2024-88", "supplemental", html)
    assert [(r["from_item"], r["to_item"], r["fund_raw"]) for r in rows] == [
        (None, "1599-0514", "Transitional Escrow Fund")
    ]


def test_transfer_source_with_to_in_its_description():
    # 2023-2 §76: "related to the planning" is part of the source, item 1599-6077; the money goes
    # to a trust fund, so there is no destination item
    html = (
        "<p>SECTION 76. Notwithstanding any general or special law to the contrary, the executive"
        " office of administration and finance shall transfer $250,000 from the startup costs for"
        " Revolution 250 related to the planning and celebration of the commonwealth’s 250th"
        " anniversary of the American Revolution established in item 1599-6077 of section 2A of"
        " chapter 268 of the acts of 2022 to the Massachusetts Tourism Trust Fund established in"
        " section 13T of chapter 23A of the General Laws.</p>"
    )
    rows, _ = read_amendments.read_law("2023-2", "supplemental", html)
    assert [(r["from_item"], r["to_item"], r["amount"]) for r in rows] == [
        ("1599-6077", None, 250000)
    ]


def test_misprinted_figure_is_low_confidence():
    # 2022-42 §46 strikes "$15,000,0000", a misprint in 2021 ch. 102, not $150,000,000: the row
    # would otherwise read as a $135,000,000 cut
    html = (
        "<p>SECTION 46. Item 1599-2026 of section 2A of chapter 102 of the acts of 2021 is hereby"
        " further amended by striking out the figure “$15,000,0000” and inserting in place thereof"
        " the following figure:- $15,000,000.</p>"
    )
    rows, _ = read_amendments.read_law("2022-42", "supplemental", html)
    assert [(r["action_type"], r["target_law_key"], r["confidence"]) for r in rows] == [
        ("figure_change", "2021-102", "low")
    ]
    assert not read_amendments._misprinted_figure("$9,310,231, $1,000 and $5,000,")


def test_clause_of_an_item_is_an_item_amendment():
    # 2024-150 §61 rewrites a proviso in "Clause (2) of item 3722-8899"; no dollars involved
    html = (
        "<p>SECTION 61. Clause (2) of item 3722-8899 of section 2 of chapter 494 of the acts of"
        " 1993 is hereby amended by striking out the words “provided, that said property shall not"
        " be released from such restriction” and inserting in place thereof the following words:-"
        " provided, that said property shall not be released from such restriction unless and"
        " until there has been a disposition of the property.</p>"
    )
    rows, unread = read_amendments.read_law("2024-150", "bond", html)
    found = [
        (r["action_type"], r["target_law_key"], r["target_section"], r["target_item"]) for r in rows
    ]
    assert found == [("purpose_change", "1993-494", "2", "3722-8899")]
    assert unread == []


def test_amendment_naming_an_item_without_a_row_is_listed():
    # 2021-24 §73 replaces a subsection of an earlier outside section whose new text names an
    # item; no pattern reads it, so a human must see it, even with no dollar sign
    html = (
        "<p>SECTION 73. Section 58 of chapter 228 of the acts of 2018 is hereby amended by striking"
        " out subsection (b) and inserting in place thereof the following subsection:-</p>"
        "<p>(b) Funds made available in item 7003-1206 shall be used for the program.</p>"
    )
    rows, unread = read_amendments.read_law("2021-24", "gaa", html)
    assert rows == []
    assert [(u["section"], u["reason"]) for u in unread] == [
        ("73", "amends text that names a line item but matched no pattern")
    ]


def test_outside_section_listing_items_is_listed():
    # 2023-2 §3 lists capital items itself; read_items stops at §3, so no stage reads them
    html = (
        "<p>SECTION 3. To provide for a program of housing, the sums set forth in sections 3 to"
        " 3B, inclusive, are hereby made available, subject to the laws regulating the"
        " disbursement of public funds.</p>"
        "<p>EXECUTIVE OFFICE OF HOUSING AND ECONOMIC DEVELOPMENT</p>"
        "<p>7002-8048.. For the MassWorks infrastructure program.......... $400,000,000</p>"
    )
    rows, unread = read_amendments.read_law("2023-2", "supplemental", html)
    assert rows == []
    assert [(u["section"], u["reason"]) for u in unread] == [
        ("3", "lists line items itself, which no stage reads")
    ]
    # read_items reads §2 of an "other" law, so its items aren't listed here
    other = html.replace("SECTION 3.", "SECTION 2.")
    assert read_amendments.read_law("2020-316", "other", other)[1] == []
    # The real 2023-2 also borrows for §3 (§77), so read_bonds reads its items (Q25): not listed
    borrowing = (
        "<p>SECTION 77. Notwithstanding any general or special law to the contrary, to meet the"
        " expenditures necessary in carrying out section 3, the state treasurer shall, upon receipt"
        " of a request by the governor, issue and sell bonds of the commonwealth in an amount to be"
        " specified by the governor from time to time but not exceeding, in the aggregate,"
        " $400,000,000.</p>"
    )
    assert read_amendments.read_law("2023-2", "supplemental", html + borrowing) == ([], [])


def test_run_reports_only_in_scope_laws_and_skips_hand_kept(root, tmp_path, capsys):
    # A reference-only law is read for its items' history, but its unread sections don't affect
    # the dataset, so they're counted, not reported. A hand-kept law has no cached text.
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.toml").write_bytes((root / "config" / "settings.toml").read_bytes())
    header = ",".join(schemas.columns("law_list"))
    laws = [
        "2024-150,2024,150,2024-11-14,,,,bond,in_scope,,,,auto,",
        "2002-244,2002,244,2002-08-10,,,,bond,reference_only,,,,auto,",
        "1993-52,1993,52,1993-05-21,,,,bond,reference_only,,,,manual,",
    ]
    (config / "law_list.csv").write_text("\n".join([header, *laws]) + "\n", "utf-8")
    unmatched = (
        "<p>SECTION 5. The department may make grants of up to $10,000 from the appropriation in"
        " section 2 for supportive services.</p>"
    )
    wording = (
        "<p>SECTION 15. Item 4000-8200 of section 2 of chapter 52 of the acts of 1993 is hereby"
        ' amended by striking out the word "thirty" and inserting in place thereof the following'
        " figure:- 50.</p>"
    )
    for acts_year, chapter, html in (
        ("2024", "150", unmatched),
        ("2002", "244", unmatched + wording),
    ):
        path = tmp_path / "raw" / "sessionlaws" / acts_year / f"{chapter}.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ChapterText": html}), "utf-8")
    ctx = Context(
        root=tmp_path,
        raw_dir=tmp_path / "raw",
        interim_dir=tmp_path / "interim",
        reports_dir=tmp_path / "reports",
        offline=True,
    )
    assert read_amendments.run(ctx) == 0
    _, unread = schemas.read_csv(tmp_path / "reports" / "unread_sections.csv")
    assert [(r["law_key"], r["section"]) for r in unread] == [("2024-150", "5")]
    _, rows = schemas.read_csv(tmp_path / "interim" / "amendments_raw.csv")
    assert [(r["law_key"], r["section"], r["target_item"]) for r in rows] == [
        ("2002-244", "15", "4000-8200")
    ]
    out = capsys.readouterr().out
    assert "1 unread sections in reference-only laws (not reported)" in out
    assert "no cached text" not in out


def test_general_laws_named_in_other_ways():
    # None of these amend an appropriation act, so they give no rows and nothing unread: a bare
    # "Chapter 40R" (2020-358 §45), "The General Laws" (§56), "as so appearing" (§58), a chapter
    # with a half and the "Official Edition" (2020-383 §8), and a resolve (2022-126 §105)
    html = (
        "<p>SECTION 45. Chapter 40R is hereby amended by striking out section 14 and inserting in"
        " place thereof the following section:-</p>"
        "<p>Section 14. The fund may receive $5,000 appropriated in item 1599-0001.</p>"
        "<p>SECTION 56. The General Laws are hereby amended by inserting after chapter 40W the"
        " following chapter:-</p><p>Chapter 40X. Any appropriation of $1,000 for this purpose.</p>"
        "<p>SECTION 58. Section 6I of said chapter 62, as so appearing, is hereby amended by"
        ' striking out the figure "$20,000,000" and inserting in place thereof the following'
        " figure:- $40,000,000.</p>"
        "<p>SECTION 60. Section 1 of chapter 159A1⁄2 of the General Laws, as appearing in the 2018"
        " Official Edition, is hereby amended by adding the following words:- or an appropriation"
        " of $6,000,000.</p>"
        "<p>SECTION 61. Said chapter 159A1⁄2 is hereby further amended by adding the following"
        " section:-</p><p>Section 13. Item 1599-0002 shall not exceed $10.</p>"
        "<p>SECTION 105. Chapter 145 of the resolves of 1957 is hereby further amended by"
        ' inserting after the word "Scott" the following words:- , Elizabeth Johnson, Jr.</p>'
    )
    assert read_amendments.read_law("2020-358", "bond", html) == ([], [])


def test_item_renumbered():
    # 2021-102 §46 renumbers an item of a 2018 bond law: no money changes
    html = (
        "<p>SECTION 46. Section 2 of chapter 112 of the acts of 2018 is hereby amended by striking"
        " out the figure “7002-0015” and inserting in place thereof the following figure:-"
        " 7002-0016.</p>"
    )
    rows, unread = read_amendments.read_law("2021-102", "surplus", html)
    assert [
        (r["action_type"], r["target_law_key"], r["target_section"], r["target_item"], r["to_item"])
        for r in rows
    ] == [("purpose_change", "2018-112", "2", "7002-0015", "7002-0016")]
    assert unread == []


def test_borrowing_sections_of_bond_laws_are_left_to_read_bonds():
    # 2021-15 §6: a borrowing limit for one item, which read_bonds reads (§7.16)
    html = (
        "<p>SECTION 2.</p><p>4000-2026 For a program ...... $10</p>"
        "<p>SECTION 6. To meet the expenditures necessary in carrying out item 4000-2026 of"
        " section 2, the state treasurer shall, upon request of the governor, issue and sell"
        " bonds of the commonwealth in an amount to be specified by the governor from time to time"
        " but not exceeding, in the aggregate, $10.</p>"
    )
    assert read_amendments.read_law("2021-15", "bond", html) == ([], [])


def test_section_returned_with_amendment_is_not_law_in_that_chapter():
    # 2021-24 §102: the Legislature's version became 2021 ch. 33, so this one gives no rows
    html = (
        "<p>The Governor returned the following section with recommendation of amendment, for"
        " message see House, No. 4004.</p>"
        "<p><s>SECTION 102. Notwithstanding any general or special law to the contrary, the"
        " comptroller shall, not later than September 1, 2021, transfer $250,000,000 from the"
        " General Fund to the Commonwealth’s Pension Liability Fund.</s></p>"
        "<p>The Governor returned the following section with recommendation of amendment, for"
        " message see House, No. 4004.</p>"
        "<p><s>SECTION 101A. Section 7 of chapter 62 of the General Laws is hereby amended by"
        " adding the following words:- or a regulation.</s></p>"
    )
    rows, unread = read_amendments.read_law("2021-24", "gaa", html)
    assert rows == []
    # listed only when it would have given rows; a wording change to the General Laws isn't
    assert [(u["section"], u["reason"][:40]) for u in unread] == [
        ("102", "returned by the Governor with a recommen")
    ]


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


def test_samples_match_hand_checked_rows(output):
    # tests/samples/expected/amendments_raw_selected.csv: a row of each action_type the samples
    # have (none strikes an item; 2022-268 §228 does, tested above)
    _, rows = schemas.read_csv(output.interim_dir / "amendments_raw.csv")
    header, expected = schemas.read_csv(
        ROOT / "tests" / "samples" / "expected" / "amendments_raw_selected.csv"
    )
    assert {e["action_type"] for e in expected} == {r["action_type"] for r in rows}
    for e in expected:
        key = (e["law_key"], e["section"], e["action_type"], e["target_item"])
        found = [
            r
            for r in rows
            if (r["law_key"], r["section"], r["action_type"], r["target_item"]) == key
        ]
        assert len(found) == 1, key
        assert {c: found[0][c] for c in header} == e


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
