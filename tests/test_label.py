import csv

from ma_approps import label, schemas
from ma_approps.context import Context

ENV = "Environment and natural resources"
KIDS = "Children and families"


def cthru(line_item, fy, dept="", original=0, supplemental=0, rr=0):
    row = dict.fromkeys(schemas.columns("cthru_line_items"), "")
    row.update(
        line_item=line_item, fiscal_year=str(fy), department_code=dept,
        original_enacted=str(original), supplemental=str(supplemental),
        retained_revenue_ceiling=str(rr), total_enacted=str(original + supplemental),
    )
    return row


def action(record_id, line_item, fy, funding_action="ORIG", amount=1000):
    row = dict.fromkeys(schemas.columns("funding_actions"), "")
    row.update(
        record_id=record_id, line_item=line_item, fiscal_year=str(fy),
        funding_action=funding_action, amount=str(amount),
    )
    return row


CATALOG = {
    "2330-0100": {"line_item": "2330-0100", "policy_area": ENV, "label_every_year": "false"},
    "1599-0026": {"line_item": "1599-0026", "policy_area": "General local aid",
                  "label_every_year": "true"},
}
DEPARTMENTS = {
    "OCA": {"department_code": "OCA", "policy_area": KIDS, "mixed": "false"},
    "ANF": {"department_code": "ANF", "policy_area": "", "mixed": "true"},
}
CTHRU = {
    ("0930-0100", 2024): cthru("0930-0100", 2024, dept="OCA"),
    ("1599-9999", 2024): cthru("1599-9999", 2024, dept="ANF"),
}


def test_policy_area_comes_from_the_catalog_first():
    assert label.policy_area("2330-0100", 2024, CATALOG, DEPARTMENTS, CTHRU) == (ENV, "catalog")


def test_label_every_year_items_go_to_review():
    assert label.policy_area("1599-0026", 2024, CATALOG, DEPARTMENTS, CTHRU) == ("", "")


def test_new_item_takes_its_department_area():
    assert label.policy_area("0930-0100", 2024, CATALOG, DEPARTMENTS, CTHRU) == (
        KIDS, "department",
    )


def test_mixed_department_or_no_cthru_row_goes_to_review():
    assert label.policy_area("1599-9999", 2024, CATALOG, DEPARTMENTS, CTHRU) == ("", "")
    assert label.policy_area("7004-0024", 2024, CATALOG, DEPARTMENTS, CTHRU) == ("", "")


def test_previously_funded_means_the_year_before_only():
    funded, _ = label.funded_years(
        [cthru("0930-0100", 2023, original=4_400_000), cthru("2330-0100", 2022, original=5)],
        [action("x", "4000-0001", 2023, "NEW")],
    )
    assert label.previously_funded("0930-0100", 2024, funded) == "Yes"
    assert label.previously_funded("4000-0001", 2024, funded) == "Yes"  # supplemental only
    assert label.previously_funded("2330-0100", 2024, funded) == "No"  # two years back
    assert label.previously_funded("", 2024, funded) == "Unknown"


def test_a_reduction_to_zero_is_not_funded():
    rows = [action("a", "1234-5678", 2023, "NEW", 500), action("b", "1234-5678", 2023, "RED", -500)]
    funded, _ = label.funded_years([], rows)
    assert label.previously_funded("1234-5678", 2024, funded) == "No"


def test_recurring_means_two_gaas_in_a_row_including_first_years():
    _, gaa = label.funded_years(
        [cthru("1111-0001", 2023, original=1), cthru("1111-0001", 2024, original=1),
         cthru("2222-0002", 2024, rr=1), cthru("2222-0002", 2025, original=1),
         cthru("3333-0003", 2024, original=1), cthru("3333-0003", 2025, supplemental=1)],
        [],
    )
    assert label.one_time_or_recurring(action("a", "1111-0001", 2024), gaa) == "Recurring"
    assert label.one_time_or_recurring(action("b", "2222-0002", 2024), gaa) == "Recurring"
    # In FY2025 only through a supplemental, so the FY2024 GAA row stands alone
    assert label.one_time_or_recurring(action("c", "3333-0003", 2024), gaa) == "One-time"


def test_supplemental_rows_are_one_time_and_others_not_classified():
    gaa = {("1111-0001", 2023), ("1111-0001", 2024)}
    assert label.one_time_or_recurring(action("a", "1111-0001", 2024, "INC"), gaa) == "One-time"
    assert label.one_time_or_recurring(action("b", "1111-0001", 2024, "REAUTH"), gaa) == (
        "Not classified"
    )
    assert label.one_time_or_recurring(action("c", "", 2024, "INT"), gaa) == "Not classified"


def test_run_writes_a_valid_labels_file(tmp_path):
    (tmp_path / "config").mkdir()
    interim = tmp_path / "data" / "interim"
    interim.mkdir(parents=True)

    def write(path, table, rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=schemas.columns(table), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    write(interim / "funding_actions.csv", "funding_actions", [
        action("2023-077-S178-2330-0100-INC-1", "2330-0100", 2024, "INC", 350_000),
        action("2023-028-S2-0930-0100-ORIG-1", "0930-0100", 2024, "ORIG", 6_077_671),
    ])
    write(interim / "cthru_line_items.csv", "cthru_line_items", [
        cthru("0930-0100", 2023, dept="OCA", original=4_400_000),
        cthru("0930-0100", 2024, dept="OCA", original=6_077_671),
        cthru("2330-0100", 2023, dept="FWE", original=9_523_813),
        cthru("2330-0100", 2024, dept="FWE", original=9_310_231, supplemental=350_000),
    ])
    write(tmp_path / "config" / "line_item_catalog.csv", "line_item_catalog",
          [dict(CATALOG["2330-0100"], decided_by="", decided_on="", note="")])
    write(tmp_path / "config" / "department_policy_areas.csv", "department_policy_areas",
          [dict(DEPARTMENTS["OCA"], department_name="", decided_by="", decided_on="", note="")])

    ctx = Context(root=tmp_path, settings={"scope": {}})
    assert label.run(ctx) == 0
    path = interim / "labels.csv"
    assert schemas.validate_file("labels", path) == []
    rows = {r["record_id"]: r for r in schemas.read_csv(path)[1]}
    ex1, ex4 = rows["2023-028-S2-0930-0100-ORIG-1"], rows["2023-077-S178-2330-0100-INC-1"]
    assert (ex1["policy_area"], ex1["policy_area_method"]) == (KIDS, "department")
    assert (ex1["previously_funded"], ex1["one_time_or_recurring"]) == ("Yes", "Recurring")
    assert (ex4["policy_area"], ex4["policy_area_method"]) == (ENV, "catalog")
    assert (ex4["previously_funded"], ex4["one_time_or_recurring"]) == ("Yes", "One-time")
    assert ex4["new_or_reapprop"] == "Pending"


def test_run_reports_missing_inputs(tmp_path):
    ctx = Context(root=tmp_path, settings={"scope": {}})
    assert label.run(ctx) == 1
