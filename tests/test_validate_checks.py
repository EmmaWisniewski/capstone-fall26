"""§13 check 4 (CTHRU comparison) and check 7 (bond totals), on small hand-made tables."""

from ma_approps import validate


def action(**kw):
    row = {
        "record_id": "R", "law_key": "2024-140", "section": "2", "line_item": "1000-0001",
        "target_law_key": kw.get("law_key", "2024-140"), "fiscal_year": "2025",
        "funding_action": "ORIG", "amount_kind": "appropriation", "amount": "100",
        "counts_toward_total": "true", "flags": "", "section_type": "approp_main",
    }
    row.update(kw)
    return row


def cthru(line_item="1000-0001", fy="2025", **kw):
    row = {
        "fiscal_year": fy, "line_item": line_item, "original_enacted": "", "supplemental": "",
        "retained_revenue_ceiling": "",
    }
    row.update(kw)
    return row


LAWS = [{"law_key": "2024-140", "role": "in_scope", "law_type": "gaa", "primary_fy": "2025"}]


def run_cthru(actions, rows):
    return validate.check_cthru(actions, rows, LAWS)


def by_status(report):
    return {(r["check"], r["line_item"]): r["status"] for r in report}


# -- CTHRU comparison ------------------------------------------------------------------------


def test_gaa_amount_equal_to_cthru_is_a_match():
    matched, report = run_cthru([action()], [cthru(original_enacted="100")])
    assert (matched, report) == (1, [])


def test_gaa_difference_is_unexplained_unless_flagged():
    actions = [action(), action(line_item="1000-0002", flags="cthru_mismatch")]
    rows = [cthru(original_enacted="150"), cthru("1000-0002", original_enacted="150")]
    _, report = run_cthru(actions, rows)
    assert by_status(report) == {
        ("gaa", "1000-0001"): "unexplained",
        ("gaa", "1000-0002"): "flagged",
    }
    first = report[0]
    assert (first["difference"], first["percent"]) == (-50, "-33.3")


def test_cthru_money_with_no_row_is_missing_and_our_money_not_in_cthru():
    actions = [action(), action(line_item="1000-0003", amount="5")]
    rows = [cthru(original_enacted="100"), cthru("1000-0002", original_enacted="70")]
    _, report = run_cthru(actions, rows)
    assert by_status(report) == {
        ("gaa", "1000-0002"): "missing_in_data",
        ("gaa", "1000-0003"): "not_in_cthru",
    }


def test_item_vetoed_to_zero_matches_an_item_cthru_leaves_out():
    matched, report = run_cthru([action(amount="0")], [cthru(original_enacted="")])
    assert (matched, report) == (1, [])


def test_years_whose_gaa_is_not_in_scope_are_not_compared():
    # FY2021's budget law is outside the window, though a stray FY2021 §2B row may exist
    actions = [action(), action(fiscal_year="2021", section_type="isf", amount="7")]
    rows = [cthru(original_enacted="100"), cthru(fy="2021", original_enacted="900")]
    matched, report = run_cthru(actions, rows)
    assert (matched, report) == (1, [])


def test_federal_grant_rows_are_left_out_because_cthru_does_not_carry_them():
    actions = [action(), action(line_item="1000-0009", section_type="federal_grants", amount="50")]
    matched, report = run_cthru(actions, [cthru(original_enacted="100")])
    assert (matched, report) == (1, [])


def test_supplemental_increases_are_deltas_and_still_count():
    actions = [
        action(),
        action(funding_action="INC", amount_kind="delta", law_key="2025-9", amount="30"),
    ]
    matched, report = run_cthru(actions, [cthru(original_enacted="100", supplemental="30")])
    assert (matched, report) == (2, [])


def test_supplementals_add_new_inc_and_red_and_leave_out_uncounted_rows():
    actions = [
        action(),
        action(funding_action="NEW", law_key="2025-9", amount="40"),
        action(funding_action="RED", law_key="2025-9", amount="-10"),
        action(funding_action="INC", law_key="2025-9", amount="999", counts_toward_total="false"),
    ]
    matched, report = run_cthru(
        actions, [cthru(original_enacted="100", supplemental="30")]
    )
    assert (matched, report) == (2, [])


def test_supplemental_difference_across_several_laws_cannot_be_attributed():
    actions = [
        action(),
        action(funding_action="NEW", law_key="2025-9", amount="40"),
        action(funding_action="INC", law_key="2025-30", amount="10"),
    ]
    _, report = run_cthru(actions, [cthru(original_enacted="100", supplemental="30")])
    assert by_status(report) == {("supplemental", "1000-0001"): "several_laws"}
    assert report[0]["laws"] == "2025-30;2025-9"


def test_retained_revenue_ceilings_are_compared_separately():
    actions = [action(amount_kind="retained_revenue_ceiling", amount="50")]
    _, report = run_cthru(
        actions, [cthru(original_enacted="", retained_revenue_ceiling="60")]
    )
    assert by_status(report) == {("retained_revenue", "1000-0001"): "unexplained"}


# -- Bond totals ---------------------------------------------------------------------------


def limit(**kw):
    row = {
        "law_key": "2024-139", "section": "3", "covers_sections": "2", "covers_items": "",
        "authorized": "300", "bond_name": "IT bonds",
    }
    row.update(kw)
    return row


def cap(line_item, amount, law_key="2024-139", **kw):
    return action(
        law_key=law_key, section="2", line_item=line_item, funding_action="CAP", amount=amount,
        counts_toward_total="false", **kw,
    )


def test_bond_items_that_add_up_to_the_limit_match():
    matched, report = validate.check_bond_totals(
        [cap("1000-0001", "100"), cap("1000-0002", "200")], [limit()]
    )
    assert (matched, report) == (1, [])


def test_bond_gap_is_reported_with_a_note_naming_the_limit():
    matched, report = validate.check_bond_totals(
        [cap("1000-0001", "100"), cap("1000-0002", "150")], [limit()]
    )
    assert matched == 0
    (row,) = report
    assert (row["status"], row["difference"], row["items_count"]) == ("differs", -50, 2)
    assert row["line_items"] == "1000-0001;1000-0002"
    assert "IT bonds (2024-139 §3)" in row["note"] and "$250 against $300" in row["note"]


def test_limit_that_names_its_items_covers_only_those():
    lim = limit(covers_sections="", covers_items="1000-0001", authorized="100")
    matched, report = validate.check_bond_totals(
        [cap("1000-0001", "100"), cap("1000-0002", "7")], [lim]
    )
    assert matched == 1
    assert [r["status"] for r in report] == ["no_limit"]
    assert report[0]["line_items"] == "1000-0002"


def test_limits_of_laws_that_are_not_in_scope_are_skipped():
    laws = [{"law_key": "2024-139", "role": "reference_only"}]
    assert validate.check_bond_totals([], [limit()], laws) == (0, [])


def test_limit_with_no_items_and_other_laws_cap_rows():
    restated = cap("1000-0001", "40", law_key="2025-17", target_law_key="2024-139")
    matched, report = validate.check_bond_totals([restated], [limit()])
    assert matched == 0
    assert [(r["status"], r["items_total"]) for r in report] == [("no_items", 0)]
