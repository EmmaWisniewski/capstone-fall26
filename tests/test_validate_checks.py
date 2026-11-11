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


def test_supplementals_add_new_inc_and_red_whether_or_not_they_count():
    # CTHRU carries federal and ARPA money too, so a row that doesn't count toward the operating
    # total still belongs in the comparison
    actions = [
        action(),
        action(funding_action="NEW", law_key="2025-9", amount="40"),
        action(funding_action="RED", law_key="2025-9", amount="-15"),
        action(funding_action="INC", law_key="2025-9", amount="5", counts_toward_total="false"),
    ]
    matched, report = run_cthru(
        actions, [cthru(original_enacted="100", supplemental="30")]
    )
    assert (matched, report) == (2, [])


def test_supplemental_difference_across_several_laws_is_still_unexplained():
    # CTHRU's supplemental figure is the total of every law, so several laws must still add up
    actions = [
        action(),
        action(funding_action="NEW", law_key="2025-9", amount="40"),
        action(funding_action="INC", law_key="2025-30", amount="10"),
    ]
    _, report = run_cthru(actions, [cthru(original_enacted="100", supplemental="30")])
    assert by_status(report) == {("supplemental", "1000-0001"): "unexplained"}
    assert report[0]["laws"] == "2025-30;2025-9"


def test_supplementals_to_a_year_whose_gaa_is_not_in_scope_are_compared():
    # Laws approved in 2021 change FY2021 items. Only items we have rows for are compared, and
    # a shortfall is earlier_laws: CTHRU's total also holds supplementals approved in 2020.
    def inc(item, amount):
        return action(line_item=item, fiscal_year="2021", funding_action="INC",
                      amount_kind="delta", law_key="2021-29", amount=amount)

    actions = [action(), inc("1000-0002", "30"), inc("1000-0003", "10"), inc("1000-0004", "90")]
    rows = [
        cthru(original_enacted="100"),
        cthru("1000-0002", fy="2021", original_enacted="900", supplemental="30"),
        cthru("1000-0003", fy="2021", supplemental="25"),  # 15 from a 2020 law
        cthru("1000-0004", fy="2021", supplemental="60"),
        cthru("1000-0005", fy="2021", supplemental="70"),  # no row of ours: not compared
    ]
    matched, report = run_cthru(actions, rows)
    assert matched == 2
    assert by_status(report) == {
        ("supplemental", "1000-0003"): "earlier_laws",
        ("supplemental", "1000-0004"): "unexplained",  # ours is above CTHRU's total
    }


def test_retained_revenue_ceilings_are_compared_separately():
    actions = [action(amount_kind="retained_revenue_ceiling", amount="50")]
    _, report = run_cthru(
        actions, [cthru(original_enacted="", retained_revenue_ceiling="60")]
    )
    assert by_status(report) == {("retained_revenue", "1000-0001"): "unexplained"}


def test_chargebacks_are_compared_with_cthrus_ceiling_not_its_original_amount():
    # CTHRU shows §2B accounts at $0 enacted with a retained-revenue ceiling
    actions = [action(section_type="isf", amount="70", flags="isf_chargeback")]
    rows = [cthru(original_enacted="", retained_revenue_ceiling="70")]
    assert run_cthru(actions, rows) == (1, [])


def test_chargebacks_cthru_lacks_are_reported_once_as_ceilings():
    # FY2025 lists only 12 chargeback accounts (issue #36): ours with no CTHRU ceiling show here
    actions = [action(section_type="isf", amount="70")]
    _, report = run_cthru(actions, [cthru("1000-0009", retained_revenue_ceiling="5")])
    assert by_status(report) == {
        ("retained_revenue", "1000-0001"): "not_in_cthru",
        ("retained_revenue", "1000-0009"): "missing_in_data",
    }


def test_an_increase_to_a_fee_revenue_item_is_added_to_its_ceiling_cthru_folds_it_in():
    actions = [
        action(amount_kind="retained_revenue_ceiling", amount="45", flags="retained_revenue"),
        action(funding_action="INC", amount_kind="delta", law_key="2024-206", amount="7"),
        action(funding_action="INC", amount_kind="delta", law_key="2024-206", amount="0"),
    ]
    rows = [cthru(retained_revenue_ceiling="52")]  # no CTHRU supplemental for the item
    assert run_cthru(actions, rows) == (1, [])


def test_a_chargeback_increase_is_added_to_the_chargeback_ceiling():
    actions = [
        action(section_type="isf", amount="100"),
        action(section_type="isf", funding_action="INC", amount_kind="delta", amount="21"),
    ]
    assert run_cthru(actions, [cthru(retained_revenue_ceiling="121")]) == (1, [])


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
