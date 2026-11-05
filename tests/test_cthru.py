"""Stage 2 `cthru` (DESIGN §3.4, §7.5), run offline on the committed CTHRU sample."""

import pytest

from ma_approps import cthru, schemas
from ma_approps.context import Context


@pytest.fixture
def cthru_rows(root, samples_dir, tmp_path):
    ctx = Context(root=root, raw_dir=samples_dir, interim_dir=tmp_path, offline=True)
    assert cthru.run(ctx) == 0
    path = tmp_path / "cthru_line_items.csv"
    assert schemas.validate_file("cthru_line_items", path) == []
    _, rows = schemas.read_csv(path)
    return {(r["fiscal_year"], r["line_item"]): r for r in rows}


def test_example_row_amounts(cthru_rows):
    # DESIGN §3.4: EX-001..003 originals and the EX-004 supplemental
    assert cthru_rows["2024", "0930-0100"]["original_enacted"] == "6077671"
    assert cthru_rows["2024", "0930-0101"]["original_enacted"] == "3750000"
    marine = cthru_rows["2024", "2330-0100"]
    assert (marine["original_enacted"], marine["supplemental"], marine["total_enacted"]) == (
        "9310231",
        "350000",
        "9660231",
    )
    assert cthru_rows["2023", "0930-0100"]["original_enacted"] == "4400000"


def test_vetoed_items_show_final_amounts(cthru_rows):
    # DESIGN §3.4 veto probe: CTHRU amounts after vetoes and overrides
    assert cthru_rows["2024", "4000-0700"]["original_enacted"] == "3601016357"
    assert cthru_rows["2024", "7061-0012"]["original_enacted"] == "498972361"
    assert cthru_rows["2024", "3000-1042"]["original_enacted"] == "35000000"
    assert cthru_rows["2024", "1231-1000"]["original_enacted"] == "1500000"  # known mismatch


def test_department_is_the_one_holding_the_money(cthru_rows):
    # 2330-0100 also has an all-zero Attorney General row in CTHRU
    marine = cthru_rows["2024", "2330-0100"]
    assert (marine["department_code"], marine["department_name"]) == (
        "FWE",
        "DEPARTMENT OF FISH AND GAME",
    )
    assert marine["secretariat"] == "ENVIRONMENTAL AFFAIRS"
    assert marine["fund_numbers"] == "0010"


def test_retained_revenue_kept_and_empty_accounts_dropped(cthru_rows):
    assert cthru_rows["2024", "0511-0003"]["retained_revenue_ceiling"] == "16000"
    # §2B ISF account: $0 in CTHRU, so not a row
    assert ("2024", "0321-2215") not in cthru_rows


def test_aggregate_sums_departments_and_formats_ids():
    rows = [
        {"fiscal_year": "2024.0", "appropriation_account_number": "12345678",
         "department_code": "AAA", "fund_number": "0010", "original_enacted_budget": "0.0"},
        {"fiscal_year": "2024.0", "appropriation_account_number": "12345678",
         "department_code": "BBB", "fund_number": "0010", "original_enacted_budget": "10.0",
         "total_enacted_budget_appropriation": "12.0", "supplemental_budget_appropriations": "2.0"},
    ]
    (row,) = cthru.aggregate(rows)
    assert (row["line_item"], row["department_code"]) == ("1234-5678", "BBB")
    assert (row["original_enacted"], row["supplemental"], row["total_enacted"]) == ("10", "2", "12")
    assert row["retained_revenue_ceiling"] == "0"


def test_aggregate_is_deterministic(samples_dir):
    rows = cthru.load_snapshot(cthru.latest_snapshot(Context(raw_dir=samples_dir)))
    assert cthru.aggregate(rows) == cthru.aggregate(list(reversed(rows)))
