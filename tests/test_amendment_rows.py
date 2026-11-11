"""Amendment rows for combine (workstream C; DESIGN §5.4, §5.5, §7.7, §10, §11.3; issue #41)."""

import pytest

from ma_approps import combine, read_amendments, read_bonds, read_items, schemas
from ma_approps.context import Context

URL = "https://malegislature.gov/Laws/SessionLaws/Acts/{acts_year}/Chapter{chapter}"


@pytest.fixture(scope="module")
def combined(tmp_path_factory, request):
    root = request.config.rootpath
    out = tmp_path_factory.mktemp("amendment_rows")
    ctx = Context(
        root=root,
        raw_dir=root / "tests" / "samples",
        interim_dir=out / "interim",
        reports_dir=out / "reports",
        offline=True,
    )
    for stage in (read_items, read_bonds, read_amendments, combine):
        assert stage.run(ctx) == 0
    _, rows = schemas.read_csv(ctx.interim_dir / "funding_actions.csv")
    _, amounts = schemas.read_csv(ctx.interim_dir / "running_amounts.csv")
    return {r["record_id"]: r for r in rows}, amounts


def _pick(row, *fields):
    return {f: row[f] for f in fields}


FIELDS = ("fiscal_year", "fy_rule", "section_type", "amount_kind", "amount", "counts_toward_total")


def test_ex004_supplemental_increase(combined):
    # 2023-77 §178 raises FY2024 item 2330-0100 from $9,310,231 to $9,660,231 (EX-004): the
    # fiscal year is the amended act's, and the running amounts record the new amount
    rows, amounts = combined
    assert _pick(rows["2023-077-S178-2330-0100-INC-1"], "target_law_key", *FIELDS) == {
        "target_law_key": "2023-28",
        "fiscal_year": "2024",
        "fy_rule": "target_act",
        "section_type": "approp_main",
        "amount_kind": "delta",
        "amount": "350000",
        "counts_toward_total": "true",
    }
    assert {
        "target_law_key": "2023-28",
        "section": "2",
        "line_item": "2330-0100",
        "as_of_event": "2023-077-S178-2330-0100-INC-1",
        "amount_after": "9660231",
    } in amounts


def test_samples(combined):
    rows, _ = combined
    # an earmark inside 0610-2000's text changes, not the item's amount (Q21): $0
    assert rows["2023-077-S175-0610-2000-INC-1"]["amount"] == "0"
    # an item inserted into the FY2024 GAA is new money
    assert _pick(rows["2023-077-S176-1599-4448-NEW-1"], "amount", "counts_toward_total") == {
        "amount": "312162361",
        "counts_toward_total": "true",
    }
    # the FY2024 interim budget is a lump sum that doesn't count (§10)
    assert _pick(rows["2023-015-S1-NOITEM-INT-1"], *FIELDS) == {
        "fiscal_year": "2024",
        "fy_rule": "stated",
        "section_type": "interim",
        "amount_kind": "interim",
        "amount": "6660000000",
        "counts_toward_total": "false",
    }
    # 2021-35 replaces an item of 2019 ch. 5, which isn't a sample, so its change is unknown
    replaced = rows["2021-035-S1-8100-1014-INC-1"]
    assert (replaced["amount"], replaced["flags"]) == ("", "low_confidence_parse")
    # transfers between funds don't count; the source fund is the row's fund
    transfer = rows["2023-077-S215-NOITEM-XFER-1"]
    assert _pick(transfer, "amount", "counts_toward_total", "fund_primary") == {
        "amount": "10000000",
        "counts_toward_total": "false",
        "fund_primary": "General Fund",
    }


def _law(key, role="in_scope", law_type="supplemental", approved="2099-12-01", fy=""):
    year, chapter = key.split("-")
    return {
        "law_key": key,
        "acts_year": year,
        "chapter": chapter,
        "approved_date": approved,
        "role": role,
        "law_type": law_type,
        "primary_fy": fy,
        "parse_strategy": "auto",
    }


LAWS = [
    _law("2099-5", law_type="gaa", approved="2099-07-01", fy="2100"),
    _law("2099-9"),
    _law("2099-8", role="reference_only"),
    _law("2098-1", law_type="bond", approved="2098-08-01"),
    _law("2099-6", law_type="interim", approved="2099-06-28", fy="2100"),
]


def _item(law, item, amount, section="2", text=""):
    return {
        "law_key": law,
        "section": section,
        "line_item": item,
        "amount": str(amount),
        "retained_revenue_ceiling": "",
        "item_text": text,
        "fy_stated": "",
    }


def _amend(section, kind, item="", old="", new="", target="2099-5", target_section="2", **kw):
    row = dict.fromkeys(schemas.columns("amendments_raw"), "")
    row.update(
        law_key="2099-9",
        section=section,
        action_type=kind,
        target_law_key=target,
        target_section=target_section,
        target_item=item,
        old_figure=str(old),
        new_figure=str(new),
        source_text=f"SECTION {section}.",
        reader_version="test",
        confidence="high",
    )
    row.update(kw)
    return row


def _rows(amendments, items, limits=()):
    amounts = combine.amendment_amounts(items, amendments, LAWS)
    rows = combine.amendment_rows(amendments, amounts, items, list(limits), LAWS, URL)
    for r in rows:
        r["counts_toward_total"] = "true" if combine.counts_toward_total(r) else "false"
    return rows


def test_actions_amounts_and_what_counts():
    items = [
        _item("2099-5", "1000-0001", 100),
        _item("2099-5", "1000-0002", 50, text="For x; provided, that not less than $20 for y"),
        _item("2099-5", "1000-0003", 40),
        _item("2099-5", "1000-0004", 30),
        _item("2099-5", "1500-0001", 10, section="2B"),
        _item("2099-5", "1599-0001", 10, section="2E"),
        _item("2099-9", "1000-0001", 25),  # this law's own §2 adds $25 for FY2100 (Q27)
    ]
    items[-1]["fy_stated"] = "2100"
    amendments = [
        _amend("10", "figure_change", "1000-0001", 100, 75),
        _amend("11", "figure_change", "1000-0002", 20, 30),  # an earmark: $0 (Q21)
        _amend("12", "item_strike", "1000-0003"),
        _amend("13", "item_replace", "1000-0004", new=30),  # same amount: wording only
        _amend("14", "figure_change", "1500-0001", 10, 15, target_section="2B"),
        _amend("15", "figure_change", "1599-0001", 10, 12, target_section="2"),  # really §2E
        _amend("16", "figure_change", "1000-0001", 75, 100),  # this law's §2 adds it (Q27)
        _amend("17", "figure_change", "1000-0009", 5, 9),  # an item no stage read
        _amend("18", "date_extend", "1000-0001", old_date="2100-06-30", new_date="2101-06-30"),
        _amend("19", "text_insert", "1000-0001"),
        _amend(
            "20",
            "transfer",
            target="",
            target_section="",
            amount="40",
            from_item="1000-0001",
            fund_raw="General Fund",
            to_fund="Stabilization Fund",
        ),
        _amend("21", "direct_appropriation", target="", target_section="", amount="60"),
        _amend("22", "figure_change", "1000-0007", 100, 1, law_key="2099-8"),  # reference-only
    ]
    found = [
        (r["section"], r["funding_action"], r["section_type"], r["amount"],
         r["counts_toward_total"], r["fiscal_year"], r["flags"])
        for r in _rows(amendments, items)
    ]  # fmt: skip
    assert found == [
        ("10", "RED", "approp_main", -25, "true", 2100, ""),
        ("11", "INC", "approp_main", 0, "true", 2100, ""),
        ("12", "RED", "approp_main", -40, "true", 2100, ""),
        ("13", "PURP", "approp_main", 0, "false", 2100, ""),
        ("14", "INC", "isf", 5, "false", 2100, "isf_chargeback"),
        ("15", "INC", "trust_transfer", 2, "false", 2100, "trust_transfer"),
        ("16", "INC", "approp_main", 0, "true", 2100, ""),
        ("17", "INC", "approp_main", 4, "true", 2100, "low_confidence_parse"),
        ("18", "REAUTH", "approp_main", "", "false", 2100, "multi_year"),
        ("19", "PURP", "approp_main", "", "false", 2100, ""),
        ("20", "XFER", "outside", 40, "false", 2100, ""),
        ("21", "NEW", "outside", 60, "true", 2100, ""),
    ]
    rows = {r["section"]: r for r in _rows(amendments, items)}
    assert rows["18"]["available_through"] == "2101-06-30"
    assert _pick(rows["20"], "line_item", "section_fund_default", "fy_rule") == {
        "line_item": "1000-0001",
        "section_fund_default": "General Fund",
        "fy_rule": "enactment_fy",
    }


def test_interim_budget_is_int():
    amendments = [
        _amend("1", "direct_appropriation", target="", target_section="", amount="900",
               law_key="2099-6")
    ]  # fmt: skip
    (row,) = _rows(amendments, [])
    assert _pick(
        row, "funding_action", "section_type", "amount_kind", "fiscal_year", "fy_rule"
    ) == {
        "funding_action": "INT",
        "section_type": "interim",
        "amount_kind": "interim",
        "fiscal_year": 2100,
        "fy_rule": "stated",
    }
    assert row["counts_toward_total"] == "false"


def test_bond_items_are_capital_authorizations():
    # issue #41: a figure change to a bond item is CAP by its change; an item restated at the
    # same amount is CAP $0 once a hand-kept row gives its starting amount; wording is PURP
    items = [_item("2098-1", "6121-2118", 70_000_000, section="2A")]
    manual = dict.fromkeys(schemas.columns("manual_rows"), "")
    manual.update(
        law_key="2098-1", section="2", line_item="4000-8200", target_law_key="2098-1",
        amount="50000000", item_text="For a housing program",
    )  # fmt: skip
    items += combine.manual_items([manual])
    limits = [
        {"law_key": "2098-1", "section": "9", "covers_sections": "2;2A", "covers_items": "",
         "available_through": "2108-06-30"},
    ]  # fmt: skip
    amendments = [
        _amend("3", "figure_change", "6121-2118", 70_000_000, 95_000_000, target="2098-1"),
        _amend("4", "item_replace", "4000-8200", new=50_000_000, target="2098-1"),
        _amend("5", "purpose_change", "6121-2118", target="2098-1", target_section="2A"),
    ]
    found = [
        (r["funding_action"], r["amount_kind"], r["section_type"], r["amount"],
         r["counts_toward_total"], r["fiscal_year"], r["available_through"])
        for r in _rows(amendments, items, limits)
    ]  # fmt: skip
    assert found == [
        ("CAP", "bond_authorization", "capital", 25_000_000, "false", 2100, "2108-06-30"),
        ("CAP", "bond_authorization", "capital", 0, "false", 2100, "2108-06-30"),
        ("PURP", "none", "capital", "", "false", 2100, "2108-06-30"),
    ]
    assert combine.capital_total(_rows(amendments, items, limits)) == 25_000_000


def test_unknown_bond_change_has_no_amount_and_is_left_out_of_the_capital_total():
    # 2024-150 §60 before the hand-kept row for 1993-52 exists: no starting amount
    amendments = [_amend("60", "item_replace", "4000-8200", new=50_000_000, target="2098-1")]
    (row,) = _rows(amendments, [])
    assert (row["funding_action"], row["amount"], row["flags"]) == (
        "CAP",
        "",
        "low_confidence_parse",
    )
    assert combine.capital_total([row]) == 0
