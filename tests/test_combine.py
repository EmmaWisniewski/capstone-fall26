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


def _item(law, item, amount, text="", fy="2099", section="2"):
    return {
        "law_key": law,
        "section": section,
        "line_item": item,
        "amount": str(amount),
        "retained_revenue_ceiling": "",
        "item_text": text,
        "fy_stated": fy,
    }


def _amend(law, section, kind, item, old="", new="", target="2098-1"):
    return {
        "law_key": law,
        "section": section,
        "action_type": kind,
        "target_law_key": target,
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



def test_a_change_to_an_overridden_item_starts_from_the_amount_cthru_shows_restored():
    # Q30: the law prints the Governor's reduced figure; CTHRU has what the Legislature restored.
    # 2024-248 §86 lowered 7006-0071 from the restored $3,332,411 to the printed $3,307,411
    laws = [
        {"law_key": "2098-1", "approved_date": "2098-07-01", "primary_fy": "2099",
         "parse_strategy": "auto", "role": "in_scope", "law_type": "gaa"},
        {"law_key": "2099-2", "approved_date": "2099-01-15", "primary_fy": "2099",
         "parse_strategy": "auto", "role": "in_scope", "law_type": "supplemental"},
    ]
    items = [
        {**_item("2098-1", "1000-0001", 3307), "veto_kind_inline": "overridden"},
        {**_item("2098-1", "1000-0002", 500), "veto_kind_inline": "overridden"},  # CTHRU below
        {**_item("2098-1", "1000-0003", 70), "veto_kind_inline": "none"},
    ]
    cthru = [
        {"fiscal_year": "2099", "line_item": "1000-0001", "original_enacted": "3332"},
        {"fiscal_year": "2099", "line_item": "1000-0002", "original_enacted": "400"},
        {"fiscal_year": "2099", "line_item": "1000-0003", "original_enacted": "90"},
    ]
    inputs = {"items_raw": items, "bond_items_raw": [], "manual_rows": [], "law_list": laws,
              "cthru_line_items": cthru}
    started = combine.starting_items(inputs)
    assert [r["amount"] for r in started] == ["3332", "500", "70"]
    amendments = [_amend("2099-2", "86", "figure_change", "1000-0001", 3332, 3307)]
    (row,) = combine.amendment_amounts(started, amendments, laws)
    assert (row["check"], row["change"]) == ("match", -25)

def test_a_carried_forward_balance_is_not_the_same_money():
    # 2021-76 §2CI carries $100,000 of 2000-0100 forward; §12's +$100,000 is new money (Q28)
    laws = [
        {"law_key": k, "approved_date": d, "primary_fy": "2099", "parse_strategy": "auto"}
        for k, d in (("2098-1", "2098-07-01"), ("2099-2", "2099-01-15"))
    ]
    items = [
        _item("2098-1", "1000-0001", 100),
        _item("2099-2", "1000-0001", 10, section="2CI"),
    ]
    amendments = [_amend("2099-2", "12", "figure_change", "1000-0001", 100, 110)]
    [row] = combine.amendment_amounts(items, amendments, laws)
    assert (row["check"], row["change"], row["note"], row["review"]) == ("match", 10, "", "false")


def test_wrong_section_named_and_target_not_read():
    laws = [
        {"law_key": k, "approved_date": d, "primary_fy": "2099", "parse_strategy": "auto"}
        for k, d in (("2098-1", "2098-07-01"), ("2099-2", "2099-01-15"))
    ]
    # 2019-142 §48 names "section 2" for an item the GAA prints in §2E
    items = [_item("2098-1", "1595-1068", 100, section="2E")]
    amendments = [
        _amend("2099-2", "48", "figure_change", "1595-1068", 100, 120),
        # 2020-151 §7–§8: two figures of an item in a law no stage read; the first may be an
        # earmark, so the item's amount stays unknown rather than becoming 37
        _amend("2099-2", "7", "figure_change", "1102-5700", 20, 37, target="2097-9"),
        _amend("2099-2", "8", "figure_change", "1102-5700", 760, 777, target="2097-9"),
    ]
    found = [
        (r["section"], r["check"], r["amount_before"], r["amount_after"], r["change"])
        for r in combine.amendment_amounts(items, amendments, laws)
    ]
    assert found == [
        ("7", "target_not_read", None, None, 17),
        ("8", "target_not_read", None, None, 17),
        ("48", "match", 100, 120, 20),
    ]
