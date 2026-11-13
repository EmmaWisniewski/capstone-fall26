"""§13 check 8: each law's status and the note in the export's last column (decided 2026-11-12)."""

from ma_approps import export, validate

LAWS = [
    {"law_key": "2023-28", "role": "in_scope", "law_type": "gaa", "primary_fy": "2024"},
    {"law_key": "2023-77", "role": "in_scope", "law_type": "supplemental", "primary_fy": "2023"},
    {"law_key": "2024-206", "role": "in_scope", "law_type": "supplemental", "primary_fy": "2024"},
    {"law_key": "2024-139", "role": "in_scope", "law_type": "bond", "primary_fy": ""},
    {"law_key": "2021-35", "role": "in_scope", "law_type": "other", "primary_fy": ""},
]


def row(law, item, amount, action="ORIG", fy="2024", **kw):
    r = {
        "record_id": f"{law}-{item}-{action}",
        "law_key": law,
        "target_law_key": law,
        "section": "2",
        "line_item": item,
        "fiscal_year": fy,
        "funding_action": action,
        "amount_kind": "delta" if action in ("INC", "RED") else "appropriation",
        "section_type": "approp_main",
        "amount": str(amount),
        "counts_toward_total": "true",
        "federal_share": "",
        "flags": "",
    }
    r.update(kw)
    return r


def cthru(item, original=0, supplemental=0, fy="2024"):
    return {
        "fiscal_year": fy,
        "line_item": item,
        "original_enacted": str(original),
        "supplemental": str(supplemental),
        "retained_revenue_ceiling": "0",
    }


def status(actions, cthru_rows, limits=()):
    return {r["law_key"]: r for r in validate.law_status(actions, cthru_rows, list(limits), LAWS)}


def test_a_budget_whose_items_all_match_is_checked():
    actions = [row("2023-28", "0930-0100", 6_077_671), row("2023-28", "0930-0101", 3_750_000)]
    got = status(actions, [cthru("0930-0100", 6_077_671), cthru("0930-0101", 3_750_000)])
    assert got["2023-28"]["status"] == "checked"
    assert got["2023-28"]["note"].startswith(
        "Total checked: 2 rows with an amount, net new $9,827,671; all 2 items compared match "
        "CTHRU FY2024 (difference $0). Excludes §2B chargebacks"
    )


def test_a_difference_gives_its_dollar_gap_with_no_tolerance():
    actions = [row("2023-28", "0930-0100", 6_077_671), row("2023-28", "0930-0101", 3_750_001)]
    got = status(actions, [cthru("0930-0100", 6_077_671), cthru("0930-0101", 3_750_000)])
    assert got["2023-28"]["status"] == "partially_checked"
    assert "1 of 2 items compared match CTHRU FY2024; 1 item differs by $1 in total" in (
        got["2023-28"]["note"]
    )


def test_a_difference_shared_with_other_laws_has_no_dollar_figure():
    # two supplementals add to one item; CTHRU's supplemental is their total, and it differs
    actions = [
        row("2023-77", "2330-0100", 350_000, "INC"),
        row("2024-206", "2330-0100", 100_000, "INC"),
    ]
    got = status(actions, [cthru("2330-0100", supplemental=400_000)])
    for law in ("2023-77", "2024-206"):
        note = got[law]["note"]
        assert got[law]["status"] == "partially_checked"
        assert "0 of 1 item compared match" in note
        assert "1 item differs but is shared with other laws" in note
        assert "differs by $" not in note


def test_a_difference_with_a_known_reason_doesnt_count_against_the_law():
    actions = [row("2023-28", "0930-0100", 6_000_000, flags="cthru_mismatch")]
    got = status(actions, [cthru("0930-0100", 6_077_671)])
    assert got["2023-28"]["status"] == "checked"
    assert "1 difference has a known reason" in got["2023-28"]["note"]


def test_nothing_to_compare_is_not_checked():
    actions = [row("2021-35", "", "", "PURP", amount_kind="none", section_type="outside")]
    got = status(actions, [cthru("0930-0100", 1)])
    assert got["2021-35"]["status"] == "not_checked"
    assert got["2021-35"]["note"].startswith("Total not checked against CTHRU.")


def limit(section, covers, authorized):
    return {
        "law_key": "2024-139",
        "section": section,
        "covers_sections": covers,
        "covers_items": "",
        "authorized": str(authorized),
        "bond_name": "FutureTech Act of 2024",
    }


def test_bond_items_are_checked_against_their_borrowing_limits():
    actions = [
        row("2024-139", "1790-3014", 750, "CAP", section="2A", section_type="capital",
            amount_kind="bond_authorization", counts_toward_total="false"),
        row("2024-139", "1790-3015", 100, "CAP", section="2C", section_type="capital",
            amount_kind="bond_authorization", counts_toward_total="false"),
    ]
    got = status(actions, [], [limit("4", "2A", 750), limit("5", "2C", 100)])
    assert got["2024-139"]["status"] == "checked"
    assert got["2024-139"]["note"] == (
        "Total checked: Capital authorizations $850 (not counted in operating totals); all 2 "
        "borrowing limits match their items."
    )
    got = status(actions, [], [limit("4", "2A", 700), limit("5", "2C", 100)])
    assert got["2024-139"]["status"] == "partially_checked"
    assert "1 of 2 borrowing limits match their items, and 1 differs by $50 in total" in (
        got["2024-139"]["note"]
    )


def test_the_main_file_repeats_the_law_s_note_on_each_row():
    settings = {"scope": {"approved_from": "2021-01-01", "approved_to": "2025-12-31"}}
    law_list = [{"law_key": "2023-28", "acts_year": "2023", "chapter": "28", "law_name": "GAA"}]
    actions = [
        dict(row("2023-28", item, 1), event_date="2023-08-09", calendar_year="2023",
             veto_status="none", agency_header_raw="", source_url="")
        for item in ("0930-0100", "0930-0101")
    ]
    rows, _ = export.main_rows(actions, law_list, [], [], [], settings, {"2023-28": "Note."})
    assert [r["Source or calculation for total"] for r in rows] == ["Note.", "Note."]
    rows, _ = export.main_rows(actions, law_list, [], [], [], settings)
    assert rows[0]["Source or calculation for total"] == export.TOTAL_NOT_CHECKED
