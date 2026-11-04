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


def test_earmark_figure_is_low_confidence(rows):
    # §81 changes "$320,000" "both times it appears" inside 3000-7040's text: maybe an earmark
    assert rows[("2023-77", "81", "3000-7040")]["confidence"] == "low"


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
    assert ("2023-77", "214") in {(r["law_key"], r["section"]) for r in unread}


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
