"""combine: items' running amounts and the struck-figure check (DESIGN §5.5, §13 check 3)."""

import pytest

from ma_approps import combine, read_amendments, read_bonds, read_items, validate
from ma_approps.context import Context


@pytest.fixture(scope="module")
def sample_amounts(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("combine")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    for stage in (read_items, read_bonds, read_amendments):
        assert stage.run(ctx) == 0
    rows = validate.check_amendment_amounts(ctx)
    return {(r["law_key"], r["section"], r["target_item"]): r for r in rows}


def _pick(row):
    return {k: row[k] for k in ("amount_before", "amount_after", "change", "check", "review")}


def test_ex004_struck_figure_matches_the_fy2024_budget(sample_amounts):
    # 2023-77 §178 strikes "$9,310,231", the FY2024 GAA's amount for 2330-0100 (EX-003/EX-004)
    assert _pick(sample_amounts["2023-77", "178", "2330-0100"]) == {
        "amount_before": 9_310_231,
        "amount_after": 9_660_231,
        "change": 350_000,
        "check": "match",
        "review": "false",
    }


def test_samples(sample_amounts):
    # §175 strikes an earmark inside 0610-2000's text, not the item's $2,803,626 (Q21)
    assert _pick(sample_amounts["2023-77", "175", "0610-2000"]) == {
        "amount_before": 2_803_626,
        "amount_after": 2_803_626,
        "change": 0,
        "check": "in_item_text",
        "review": "true",
    }
    # an item replaced at its own amount, and a new item inserted into the GAA
    assert sample_amounts["2024-140", "181", "4400-1031"]["change"] == 0
    assert sample_amounts["2023-77", "176", "1599-4448"]["change"] == 312_162_361
    # 2019-5 isn't a sample, so the replaced item's amount is unknown
    assert _pick(sample_amounts["2021-35", "1", "8100-1014"])["change"] is None
    # 2023-77 §2 adds $200,000 to 3000-7040 and §81 raises it by $200,000 (Q27)
    assert "Q27" in sample_amounts["2023-77", "81", "3000-7040"]["note"]
    assert {r["check"] for r in sample_amounts.values()} <= {"", *combine.CHECKS}


def _item(law, item, amount, text="", fy="2099"):
    return {
        "law_key": law,
        "section": "2",
        "line_item": item,
        "amount": str(amount),
        "retained_revenue_ceiling": "",
        "item_text": text,
        "fy_stated": fy,
    }


def _amend(law, section, kind, item, old="", new=""):
    return {
        "law_key": law,
        "section": section,
        "action_type": kind,
        "target_law_key": "2098-1",
        "target_section": "2",
        "target_item": item,
        "old_figure": str(old),
        "new_figure": str(new),
        "source_text": "",
    }


def test_date_order_text_figures_mismatches_and_strikes():
    laws = [
        {"law_key": k, "approved_date": d, "primary_fy": "2099", "parse_strategy": "auto"}
        for k, d in (("2098-1", "2098-07-01"), ("2099-2", "2099-01-15"), ("2099-3", "2099-03-01"))
    ]
    items = [
        _item("2098-1", "1000-0001", 100, "For grants; not more than $15,000,0000 for x .... $100"),
        _item("2098-1", "1000-0002", 50),
        _item("2098-1", "1000-0004", 100),
        _item("2099-2", "1000-0004", 7),  # the supplemental's own §2 item
    ]
    amendments = [
        _amend("2099-3", "5", "figure_change", "1000-0001", 120, 150),  # listed first, signed later
        _amend("2099-3", "6", "item_strike", "1000-0002"),
        _amend("2099-2", "9", "figure_change", "1000-0001", 100, 120),
        _amend("2099-2", "10", "figure_change", "1000-0001", 150_000_000, 1),  # misprint in text
        _amend("2099-2", "11", "figure_change", "1000-0002", 999, 1000),
        _amend("2099-2", "12", "figure_change", "1000-0004", 100, 107),
    ]
    found = [
        (r["law_key"], r["section"], r["check"], r["amount_after"], r["change"], "Q27" in r["note"])
        for r in combine.amendment_amounts(items, amendments, laws)
    ]
    assert found == [
        ("2099-2", "9", "match", 120, 20, False),
        ("2099-2", "10", "in_item_text", 120, 0, False),
        ("2099-2", "11", "mismatch", 1000, 1, False),  # the law's own change, sent to review
        ("2099-2", "12", "match", 107, 7, True),
        ("2099-3", "5", "match", 150, 30, False),
        ("2099-3", "6", "", 0, -1000, False),
    ]
