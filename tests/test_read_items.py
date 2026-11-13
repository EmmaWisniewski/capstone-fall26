"""read_items: line items in supplemental and annual budgets (DESIGN §7.3, §11.2)."""

import pytest

from ma_approps import read_items, schemas
from ma_approps.context import Context
from ma_approps.paragraphs import paragraphs

SECTION_1 = (
    "<p>SECTION 1. The sums set forth in section 2 are hereby appropriated from the General "
    "Fund for the fiscal year ending June 30, 2025.</p>"
)


def read(body, section_1=SECTION_1):
    items, unread = read_items.read_law("2099-1", paragraphs("2099-1", section_1 + body))
    return items, unread


def one(body, **kw):
    items, unread = read(body, **kw)
    assert len(items) == 1 and not unread, (items, unread)
    return items[0]


# -- sections -----------------------------------------------------------------


@pytest.mark.parametrize("heading", ["SECTION 2.", "SECTION 2", "Section 2"])
def test_section_2_heading_variants(heading):
    # Emma's issue #12: 2024-140 prints "SECTION 2", 2021-24 prints "Section 2"
    item = one(f"<p>{heading}</p><p>1108-5200 Plan costs ...... $240,000,000.</p>")
    assert (item["section"], item["line_item"], item["amount"]) == ("2", "1108-5200", "240000000")
    assert (item["section_fund_default"], item["fy_stated"]) == ("General Fund", "2025")


def test_section_heading_with_preamble_and_roman_numerals():
    items, _ = read(
        "<p>SECTION 2A. The sums set forth in this section are hereby appropriated from the "
        "Transitional Escrow Fund.</p><p>1599-0001 Shelter ...... $10</p>"
        "<p>SECTION 2C.I. For the purpose of making available in fiscal year 2026 balances "
        "which otherwise would revert.</p><p>1599-0002 Carried ...... $20</p>"
    )
    assert [(r["section"], r["section_fund_default"], r["fy_stated"]) for r in items] == [
        ("2A", "Transitional Escrow Fund", "2025"),
        ("2CI", "", "2026"),  # 2C sections carry forward old balances: no default fund
    ]


def test_first_outside_section_ends_the_budget_part():
    items, unread = read(
        "<p>SECTION 2.</p><p>1599-0001 A ...... $10</p>"
        "<p>SECTION 3. Section 2 of chapter 29 is amended by inserting the following:</p>"
        "<p>Section 2PPP. There shall be a fund.</p><p>1599-0002 B ...... $20</p>"
    )
    assert [r["line_item"] for r in items] == ["1599-0001"] and not unread


def test_policy_section_2_without_items_is_ignored():
    # 2021-35 "SECTION 2. (a) Notwithstanding …" is policy text, not a budget section
    assert read("<p>SECTION 2. (a) Notwithstanding any law, kits shall be tested.</p>") == ([], [])


# -- items --------------------------------------------------------------------


def test_trailing_amount_not_earmark_and_multi_paragraph():
    item = one(
        "<p>SECTION 2.</p><p>0930-0100 For the office; provided, that not less than $300,000 "
        "shall be expended for youth;</p><p>provided further, that reports are filed "
        "......... $6,077,671</p>"
    )
    assert item["amount"] == "6077671"
    assert item["item_text"] == (
        "For the office; provided, that not less than $300,000 shall be expended for youth; "
        "provided further, that reports are filed"
    )
    assert (item["para_start"], item["para_end"]) == ("2", "3")


@pytest.mark.parametrize(
    "tail, amount, confidence",
    [
        ("...... $6,077,671", "6077671", "high"),
        ("...... $240,000,000.", "240000000", "high"),  # 2025-3
        ("of the General Laws $437,250", "437250", "high"),  # no dotted leader (FY2021/FY2022)
        ("...... $186.409,929", "186409929", "medium"),  # typos in printed amounts
        ("...... 3,369,875", "3369875", "medium"),
        ("...... .$4,100,000", "4100000", "medium"),
        ("...... $$515,000", "515000", "medium"),
        ("...... $ 2,629", "2629", "medium"),
        ("...... $4,371,777.42", "4371777", "medium"),
    ],
)
def test_amount_variants(tail, amount, confidence):
    item = one(f"<p>SECTION 2.</p><p>1599-0001 For it {tail}</p>")
    assert (item["amount"], item["confidence"]) == (amount, confidence)


def test_item_id_followed_by_typo_letter():
    item = one("<p>SECTION 2.</p><p>4125-0122vFor the commission ...... $10</p>")
    assert item["line_item"] == "4125-0122" and item["item_text"] == "vFor the commission"


def test_item_without_amount_is_low_confidence():
    items, _ = read("<p>SECTION 2.</p><p>1599-0001 For it</p><p>1599-0002 Next ...... $5</p>")
    assert [(r["amount"], r["confidence"]) for r in items] == [("", "low"), ("5", "high")]


def test_retained_revenue_ceiling():
    item = one(
        "<p>SECTION 2.</p><p>0910-0210 For the office, which may expend revenues collected not "
        "more than $1,175,000 from fees ...... $1,175,000</p>"
    )
    assert (item["amount"], item["retained_revenue_ceiling"]) == ("1175000", "1175000")


def test_headers():
    items, _ = read(
        "<p>SECTION 2.</p><p>EXECUTIVE OFFICE OF ENERGY AND ENVIRONMENTAL AFFAIRS.</p>"
        "<p>Department of Fish and Game.</p><p>2330-0100 For marine fisheries ...... $9,310,231</p>"
        "<p>OFFICE OF THE CHILD ADVOCATE.</p><p>0930-0101 For the center ...... $3,750,000</p>"
    )
    assert [(r["secretariat_header_raw"], r["agency_header_raw"]) for r in items] == [
        ("EXECUTIVE OFFICE OF ENERGY AND ENVIRONMENTAL AFFAIRS.", "Department of Fish and Game."),
        ("OFFICE OF THE CHILD ADVOCATE.", ""),
    ]


def test_heading_shown_in_capitals_is_a_secretariat():
    # 2021-24 §2D: without this, EOHHS grants kept the heading above ("MASSACHUSETTS
    # DEVELOPMENTAL DISABILITIES COUNCIL.") and got the wrong agency
    items, _ = read(
        "<p>SECTION 2.</p><p>MASSACHUSETTS DEVELOPMENTAL DISABILITIES COUNCIL.</p>"
        "<p>1100-1702 For a grant ...... $5</p>"
        '<p><span style="text-transform: uppercase;">Executive office of health and human '
        "services.</span></p><p>Office of the Secretary.</p><p>4000-1315 For a grant ...... $6</p>"
    )
    assert [(r["secretariat_header_raw"], r["agency_header_raw"]) for r in items] == [
        ("MASSACHUSETTS DEVELOPMENTAL DISABILITIES COUNCIL.", ""),
        ("EXECUTIVE OFFICE OF HEALTH AND HUMAN SERVICES.", "Office of the Secretary."),
    ]


# -- vetoes and fund splits ---------------------------------------------------


def test_reduced_with_wording_keeps_final_wording_only():
    item = one(
        "<p>SECTION 2.</p><p><strong>Governor reduced the following item and disapproved of "
        "certain wording</strong><br />2210-0106 "
        '<span style="text-decoration: line-through;">For the old purpose, not more than '
        "$4,025,451</span><strong>For the new purpose, not more than $2,888,473</strong>"
        '...... <s>$4,025,451</s> $2,888,473</p>'
    )
    assert item["item_text"] == "For the new purpose, not more than $2,888,473"
    assert (item["amount"], item["amount_struck"]) == ("2888473", "4025451")
    assert item["veto_kind_inline"] == "reduced_and_wording"
    assert item["veto_annotation_raw"].startswith("Governor reduced")


def test_override_notes_and_unbolded_notes():
    item = one(
        "<p>SECTION 2.</p><p><strong>Legislature overrode Governor's disapproval</strong></p>"
        "<p>The Governor disapproved of the following item</p><p>1231-1000 For relief ...... "
        "$1,500,000</p>"
    )
    assert item["veto_kind_inline"] == "overridden"


@pytest.mark.parametrize(
    "note, amount, kind",
    [
        # issue #28: wording struck, amount unchanged (2020-383, 2021-24, 2021-102, 2022-176)
        ("Governor disapproved wording as indicated in the following item.", "$3,000,000,000",
         "wording_vetoed"),
        ("The Governor disapproved of certain wording, for message see House, No. 4019.",
         "$5,000", "wording_vetoed"),
        ("Governor disapproved of the certain wording, for message see House, No. 4288",
         "$5,000", "wording_vetoed"),
        # a wording note on an item whose amount is struck is a whole-item veto
        ("Governor disapproved certain wording in the following section", "<s>$5,000</s>",
         "disapproved"),
        # whole-item vetoes, incl. the misspelling in 2025-9 and pocket vetoes (2020-383)
        ("Governor dissaproved of the following item, for message see H4250", "$5,000",
         "disapproved"),
        ("Governor pocket vetoed the following item.", "$250,000,000", "disapproved"),
        ("The Governor disapproved of certain wording, for message see House, No. 4019. "
         "The Legislature overrode the Governor's veto.", "$5,000", "overridden"),
    ],
)
def test_veto_kinds(note, amount, kind):
    item = one(f"<p>SECTION 2.</p><p><b>{note}</b></p><p>6621-2108 For roads ...... {amount}</p>")
    assert item["veto_kind_inline"] == kind


def test_legislature_header_is_not_a_veto_note():
    # the bold "LEGISLATURE." header above item 9500-0000 (2021-24)
    item = one("<p>SECTION 2.</p><p><b>LEGISLATURE.</b></p><p>9500-0000 Senate ...... $5</p>")
    assert (item["secretariat_header_raw"], item["veto_kind_inline"]) == ("LEGISLATURE.", "none")
    assert item["veto_annotation_raw"] == ""


def test_replacement_amount_on_its_own_line():
    # 2025-9 item 1595-6368: struck amount at the end, new amount on the next line
    item = one(
        "<p>SECTION 2.</p><p><b>Governor reduced of the following item</b></p>"
        "<p>1595-6368 For a transfer ...... <s>$572,945,163</s></p><p>$558,945,163</p>"
    )
    assert (item["amount"], item["amount_struck"]) == ("558945163", "572945163")


def test_fully_struck_amount_has_no_final_amount():
    item = one("<p>SECTION 2.</p><p>1599-0001 For it ...... <s>$500,000</s></p>")
    assert (item["amount"], item["amount_struck"], item["confidence"]) == ("", "500000", "medium")


def test_fund_split_variants():
    items, unread = read(
        "<p>SECTION 2.</p>"
        "<p>0699-0015 Debt ...... $2,108,969,650</p><p>General Fund...... 52.12%<br />"
        "Commonwealth Transportation Fund...... 47.88%</p>"
        "<p>1232-0100 Tanks ...... $10,000,000</p><p>Underground Storage Tank Petroleum</p>"
        "<p>Product Cleanup Fund...... 100%</p>"  # name wrapped onto two lines
        "<p>1233-2350 Aid ...... $1,308,713,668</p><p>General Fund ...... 80.32</p>"
        "<p>Gaming Local Aid Fund ...... 19.68%</p>"  # missing % (2024-140)
        "<p>7006-0001 Cannabis ...... $5</p><p>Marijuana Regulation Fund 100%</p>"  # no leader
        "<p>2310-0200 Game $17,465,233 Inland Fisheries and Game Fund ...... 100%</p>"
    )
    assert not unread
    assert [r["fund_splits_raw"] for r in items] == [
        "General Fund:52.12;Commonwealth Transportation Fund:47.88",
        "Underground Storage Tank Petroleum Product Cleanup Fund:100",
        "General Fund:80.32;Gaming Local Aid Fund:19.68",
        "Marijuana Regulation Fund:100",
        "Inland Fisheries and Game Fund:100",
    ]
    assert items[-1]["amount"] == "17465233"


MISPRINTED = (
    "<p>SECTION 2.</p><p>5911-1002 A ...... $10</p>"
    "<p>911-1003 For the administration of the department ...... $20</p>"
)


def test_unread_paragraphs():
    # 2024-140 prints "911-1003" for item 5911-1003
    items, unread = read(MISPRINTED)
    assert len(items) == 1
    assert [(u["section"], u["para_idx"], u["explanation"]) for u in unread] == [("2", "3", "")]


def test_item_number_fixes():
    # issue #18: config/item_number_fixes.csv maps a misprinted number to the right one
    items, unread = read_items.read_law(
        "2099-1", paragraphs("2099-1", SECTION_1 + MISPRINTED), {"911-1003": "5911-1003"}
    )
    assert not unread
    fixed = items[1]
    assert (fixed["line_item"], fixed["amount"]) == ("5911-1003", "20")
    assert fixed["confidence"] == "medium"
    assert fixed["item_text"] == "For the administration of the department"


def test_item_number_fixes_file_is_valid(root):
    path = root / "config" / "item_number_fixes.csv"
    assert schemas.validate_file("item_number_fixes", path) == []
    _, rows = schemas.read_csv(path)
    assert all(schemas.LINE_ITEM_RE.match(r["line_item"]) for r in rows)


# -- samples ------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_run(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("read_items")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    assert read_items.run(ctx) == 0
    return ctx


def test_samples_match_schema(sample_run):
    path = sample_run.interim_dir / "items_raw.csv"
    assert schemas.validate_file("items_raw", path) == []


def test_samples_item_counts(sample_run):
    _, rows = schemas.read_csv(sample_run.interim_dir / "items_raw.csv")
    counts = {}
    for r in rows:
        counts.setdefault(r["law_key"], {}).setdefault(r["section"], 0)
        counts[r["law_key"]][r["section"]] += 1
    assert counts["2025-3"] == {"2": 1}
    assert counts["2023-77"] == {"2": 12, "2A": 14, "2CI": 57, "2CII": 6}
    assert sum(counts["2023-28"].values()) == 1418
    assert sum(counts["2024-140"].values()) == 1390  # incl. 5911-1003, printed "911-1003"
    assert "2021-35" not in counts  # policy act: its item is C's (inserted by an outside section)
    assert "2023-15" not in counts  # interim budget: read by read_amendments (C)


def test_samples_expected_rows(sample_run, samples_dir):
    _, rows = schemas.read_csv(sample_run.interim_dir / "items_raw.csv")
    header, expected = schemas.read_csv(samples_dir / "expected" / "items_raw_selected.csv")
    for e in expected:
        key = (e["law_key"], e["section"], e["line_item"])
        matches = [r for r in rows if (r["law_key"], r["section"], r["line_item"]) == key]
        assert len(matches) == 1, key
        assert {c: matches[0][c] for c in header} == e


def test_samples_unread(sample_run):
    _, unread = schemas.read_csv(sample_run.reports_dir / "unread_paragraphs.csv")
    assert unread == []  # the misprinted "911-1003" is fixed by config/item_number_fixes.csv
