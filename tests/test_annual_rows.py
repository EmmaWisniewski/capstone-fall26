"""combine.annual_rows and combine.annual_gaps: CTHRU's GAA amounts as original-appropriation rows
(DESIGN §3.4, §5.7, §10; workstream E)."""

from ma_approps import combine, schemas

URL = "https://malegislature.gov/Laws/SessionLaws/Acts/{acts_year}/Chapter{chapter}"


def law(key="2023-28", law_type="gaa", role="in_scope", approved="2023-08-09", fy="2024"):
    year, chapter = key.split("-")
    return {
        "law_key": key,
        "acts_year": year,
        "chapter": chapter,
        "law_type": law_type,
        "role": role,
        "approved_date": approved,
        "primary_fy": fy,
    }


def item(line_item, amount, section="2", key="2023-28", fy="2024", **kw):
    row = dict.fromkeys(schemas.columns("items_raw"), "")
    row.update(
        law_key=key,
        section=section,
        line_item=line_item,
        amount=str(amount),
        fy_stated=fy,
        section_fund_default="General Fund",
        veto_kind_inline="none",
        para_start="5",
        para_end="5",
        reader_version="0.2.0",
        confidence="high",
    )
    row.update(kw)
    return row


def cthru(line_item, original, fy="2024", funds="0010", ceiling=0):
    row = dict.fromkeys(schemas.columns("cthru_line_items"), "")
    row.update(
        fiscal_year=fy,
        line_item=line_item,
        original_enacted=str(original),
        retained_revenue_ceiling=str(ceiling),
        fund_numbers=funds,
    )
    return row


def annual(items, cthru_rows, laws=None):
    return combine.annual_rows(list(items), laws or [law()], list(cthru_rows), URL)


def flags(row):
    return [f for f in row["flags"].split(";") if f]


def test_amount_comes_from_cthru_and_the_printed_amount_is_kept():
    [row] = annual([item("0930-0100", 6077671)], [cthru("0930-0100", 6077671)])
    assert (row["funding_action"], row["amount_kind"], row["section_type"]) == (
        "ORIG",
        "appropriation",
        "approp_main",
    )
    assert (row["amount"], row["amount_source"], row["amount_printed"]) == (
        6077671,
        "cthru",
        6077671,
    )
    assert (row["veto_status"], row["flags"]) == ("none", "")
    assert (row["fiscal_year"], row["fy_rule"], row["event_date"]) == (2024, "stated", "2023-08-09")
    assert row["source_url"] == "https://malegislature.gov/Laws/SessionLaws/Acts/2023/Chapter28"
    assert row["fund_numbers"] == "0010"
    assert "record_id" not in row and "counts_toward_total" not in row  # the shared core sets them


def test_cthru_rather_than_the_law_decides_the_amount():
    [row] = annual([item("2330-0100", 9310231)], [cthru("2330-0100", 9000000)])
    assert (row["amount"], row["amount_printed"]) == (9000000, 9310231)


def test_a_marked_veto_that_cthru_confirms_is_explained():
    marked = item("4000-0700", 500, amount_struck="800", veto_kind_inline="reduced")
    [row] = annual([marked], [cthru("4000-0700", 500)])
    assert (row["amount"], row["amount_printed"], row["veto_status"]) == (500, 800, "reduced")
    assert "cthru_mismatch" not in flags(row)


def test_a_veto_the_law_text_does_not_mark_is_read_from_cthru():
    [row] = annual([item("4000-0700", 800)], [cthru("4000-0700", 500)])
    assert (row["amount"], row["veto_status"]) == (500, "reduced")
    assert "cthru_mismatch" not in flags(row)


def test_cthru_above_the_printed_amount_is_unexplained():
    [row] = annual([item("4000-0700", 500)], [cthru("4000-0700", 800)])
    assert (row["amount"], row["veto_status"]) == (800, "none")
    assert "cthru_mismatch" in flags(row)


def test_an_override_cthru_disagrees_with_is_flagged_1231_1000():
    overridden = item("1231-1000", 10000000, veto_kind_inline="overridden")
    [row] = annual([overridden], [cthru("1231-1000", 1500000)])
    assert (row["amount"], row["veto_status"]) == (1500000, "overridden")
    assert "cthru_mismatch" in flags(row)


def test_an_override_restoring_money_above_the_printed_figure_is_explained_3000_5000():
    overridden = item("3000-5000", 16500000, veto_kind_inline="overridden")
    [row] = annual([overridden], [cthru("3000-5000", 17500000)])
    assert (row["amount"], row["amount_printed"], row["veto_status"]) == (
        17500000,
        16500000,
        "overridden",
    )
    assert "cthru_mismatch" not in flags(row)


def test_an_item_cthru_does_not_list_was_vetoed_to_zero():
    [row] = annual([item("7061-0012", 5000)], [cthru("0930-0100", 100)])
    assert (row["amount"], row["amount_source"], row["veto_status"]) == (0, "cthru", "vetoed")


def test_a_fee_revenue_item_without_a_cthru_amount_takes_the_printed_ceiling():
    fee = item("4000-0320", "", retained_revenue_ceiling="225000000")
    [row] = annual([fee], [cthru("0930-0100", 100)])
    assert (row["amount"], row["amount_kind"], row["amount_source"]) == (
        225000000,
        "retained_revenue_ceiling",
        "law_text",
    )
    assert flags(row) == ["retained_revenue"]
    assert row["veto_status"] == "none"


def test_a_fiscal_year_cthru_has_not_published_falls_back_to_the_printed_amount():
    [row] = annual([item("0930-0100", 6077671)], [cthru("0930-0100", 1, fy="2023")])
    assert (row["amount"], row["amount_source"]) == (6077671, "law_text")
    assert "cthru_mismatch" in flags(row)


def test_isf_items_take_the_printed_amount_and_are_chargebacks():
    [row] = annual([item("1599-0001", 700, section="2B")], [cthru("1599-0001", 0, funds="0015")])
    assert (row["section_type"], row["amount"], row["amount_source"]) == ("isf", 700, "law_text")
    assert flags(row) == ["isf_chargeback"]


def test_an_item_cthru_books_only_to_fund_0015_is_a_chargeback_anywhere():
    [row] = annual([item("1599-0001", 700)], [cthru("1599-0001", 700, funds="0015")])
    assert "isf_chargeback" in flags(row)


def test_surtax_items_come_from_cthru():
    [row] = annual([item("7066-0050", 1)], [cthru("7066-0050", 1000, funds="2017")], [law()])
    assert row["amount"] == 1000
    row = annual([item("7066-0050", 1, section="2F")], [cthru("7066-0050", 1000, funds="2017")])[0]
    assert (row["section_type"], row["amount"]) == ("surtax", 1000)


def test_trust_transfers_come_from_cthru_but_are_not_counted():
    rows = annual([item("1595-0035", 5000000, section="2E")], [cthru("1595-0035", 5000000)])
    [row] = rows
    assert (row["section_type"], row["amount"], row["amount_source"]) == (
        "trust_transfer",
        5000000,
        "cthru",
    )
    assert flags(row) == ["trust_transfer"]
    out, _, _ = combine.combine_rows({"annual": rows}, [law()], [])
    assert out[0]["counts_toward_total"] == "false"


def test_federal_grants_are_left_to_the_federal_grant_rows():
    assert annual([item("1599-0001", 700, section="2D")], [cthru("1599-0001", 700)]) == []


def test_only_in_scope_gaas_count():
    rows = annual(
        [
            item("0930-0100", 1, key="2023-77"),
            item("0930-0101", 1, key="2021-24"),
            item("0930-0102", 1),
        ],
        [cthru("0930-0100", 1), cthru("0930-0101", 1), cthru("0930-0102", 1)],
        laws=[
            law("2023-77", "supplemental"),
            law("2021-24", role="excluded"),
            law(),
        ],
    )
    assert [r["line_item"] for r in rows] == ["0930-0102"]


def test_an_item_printed_twice_gets_cthrus_amount_once_and_both_are_flagged():
    rows = annual(
        [item("0930-0100", 100, para_start="5"), item("0930-0100", 100, para_start="9")],
        [cthru("0930-0100", 100)],
    )
    assert [r["amount"] for r in rows] == [100, 0]
    assert all("cthru_mismatch" in flags(r) for r in rows)


def test_a_printed_fund_split_wins_over_cthrus_fund():
    [row] = annual(
        [item("0930-0100", 100, fund_splits_raw="General Fund:60;Gaming Local Aid Fund:40")],
        [cthru("0930-0100", 100, funds="0010")],
    )
    assert "fund_numbers" not in row


def test_the_core_counts_original_rows_but_not_chargebacks():
    rows = annual(
        [
            item("0930-0100", 6000),
            item("1599-0001", 700, section="2B"),
            item("4000-0320", "", retained_revenue_ceiling="225"),
        ],
        [cthru("0930-0100", 6000), cthru("1599-0001", 0, funds="0015")],
    )
    out, _, _ = combine.combine_rows({"annual": rows}, [law()], [])
    assert [(r["record_id"], r["counts_toward_total"]) for r in out] == [
        ("2023-028-S2-0930-0100-ORIG-1", "true"),
        ("2023-028-S2-4000-0320-ORIG-1", "true"),  # fee-revenue ceilings count, flagged (Q2)
        ("2023-028-S2B-1599-0001-ORIG-1", "false"),
    ]
    assert combine.operating_total(out) == 6000 + 225


def test_cthru_money_with_no_item_read_is_reported():
    problems = combine.annual_gaps(
        [item("0930-0100", 6000), item("1599-0001", 700, section="2D")],
        [law()],
        [
            cthru("0930-0100", 6000),
            cthru("1599-0001", 700),  # read as a §2D item
            cthru("2330-0100", 9310231),  # not read at all
            cthru("2330-0100", 5, fy="2023"),  # a year with no in-scope GAA
        ],
    )
    assert [(p["law_key"], p["line_item"]) for p in problems] == [("2023-28", "2330-0100")]
    assert "$9,310,231" in problems[0]["problem"]
