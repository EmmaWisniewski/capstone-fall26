import csv

from ma_approps import label, schemas
from ma_approps.context import Context

ENV = "Environment and natural resources"
KIDS = "Children and families"


def cthru(line_item, fy, dept="", original=0, supplemental=0, rr=0, account="", dept_name=""):
    row = dict.fromkeys(schemas.columns("cthru_line_items"), "")
    row.update(
        line_item=line_item, fiscal_year=str(fy), department_code=dept,
        original_enacted=str(original), supplemental=str(supplemental),
        retained_revenue_ceiling=str(rr), total_enacted=str(original + supplemental),
        account_name=account, department_name=dept_name,
    )
    return row


def action(record_id, line_item, fy, funding_action="ORIG", amount=1000, text="", header=""):
    row = dict.fromkeys(schemas.columns("funding_actions"), "")
    row.update(
        record_id=record_id, line_item=line_item, fiscal_year=str(fy),
        funding_action=funding_action, amount=str(amount), item_text=text,
        agency_header_raw=header,
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


MARINE = "For the operation of the division of marine fisheries; provided, that the division may"
FWE_ACCOUNT = cthru("2330-0100", 2024, account="DIV.OF MARINE FISHERIES-ADMINISTRATION",
                    dept_name="DEPARTMENT OF FISH AND GAME")
OCA_CENTER = cthru("0930-0101", 2024, account="Center on Child Wellbeing and Trauma",
                   dept_name="OFFICE OF THE CHILD ADVOCATE")


def test_agency_is_the_office_the_law_text_names():
    row = action("a", "2330-0100", 2024, text=MARINE)
    assert label.agency_office(row, FWE_ACCOUNT) == "Division of Marine Fisheries"
    row = action("b", "0810-0014", 2024, text="For the operation of the office of ratepayer "
                 "advocacy within the office of the attorney general under section 11E")
    assert label.agency_office(row, None) == "Office of Ratepayer Advocacy"


def test_agency_falls_back_to_account_then_department_then_header():
    # An amendment row has no "For the ..." text, so the CTHRU account name names the division
    row = action("a", "2330-0100", 2024, "INC", text="Said item 2330-0100 is hereby amended")
    assert label.agency_office(row, FWE_ACCOUNT) == "Division of Marine Fisheries"
    # A program name isn't an office, so the department is used
    row = action("b", "0930-0101", 2024, text="For the operation of the state center on child "
                 "wellbeing and trauma.......... $3,750,000")
    assert label.agency_office(row, OCA_CENTER) == "Office of the Child Advocate"
    # Not in CTHRU (e.g., a bond item): the law's printed header
    row = action("c", "7004-0024", 2024, "CAP", header="Department of Fish and Game.")
    assert label.agency_office(row, None) == "Department of Fish and Game"


def test_department_names_are_cleaned_up():
    names = {
        "DEPARTMENT of AGRICULTURAL RESOURCES": "Department of Agricultural Resources",
        "EXECUTIVE OFFICE for ADMINISTRATION and FINANCE":
            "Executive Office for Administration and Finance",
        "SHERIFF DEPARTMENT SUFFOLK": "Suffolk Sheriff's Department",
        "SPRINGFIELD TECH COMM COLLEGE": "Springfield Technical Community College",
        "VETERANS' HOME IN CHELSEA": "Veterans' Home in Chelsea",
    }
    for raw, clean in names.items():
        assert label.department_display_name(raw) == clean


def test_cut_off_cthru_names_are_not_used_as_offices():
    cut_off = "Office of Commonwealth Performance, Accountability and Trans"  # 60 characters
    assert label.agency_from_account(cut_off) == ""


def test_purpose_is_the_first_clause_without_boilerplate():
    assert label.program_purpose(action("a", "2330-0100", 2024, text=MARINE), None) == (
        "Division of marine fisheries", "rule",
    )
    text = ("For the operation of the supreme judicial court, including the salaries of the chief "
            "justice and the 6 associate justices")
    assert label.program_purpose(action("b", "0320-0003", 2024, text=text), None)[0] == (
        "Supreme judicial court"
    )
    long_text = "For grants to " + "community organizations and " * 10
    purpose = label.program_purpose(action("c", "1234-5678", 2024, text=long_text), None)[0]
    assert len(purpose) <= 101 and purpose.endswith("…")


def test_purpose_falls_back_to_the_cthru_account_name():
    account = cthru("2810-0100", 2024, account="STATE PARKS AND RECREATION")
    assert label.program_purpose(action("a", "2810-0100", 2024), account) == (
        "State parks and recreation", "rule",
    )
    assert label.program_purpose(action("b", "", 2024, "INT"), None) == ("", "")


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
        action("2023-077-S178-2330-0100-INC-1", "2330-0100", 2024, "INC", 350_000,
               text="Said item 2330-0100 is hereby further amended"),
        action("2023-028-S2-0930-0100-ORIG-1", "0930-0100", 2024, "ORIG", 6_077_671,
               text="For the operation of the office of the child advocate; provided, that"),
    ])
    write(interim / "cthru_line_items.csv", "cthru_line_items", [
        cthru("0930-0100", 2023, dept="OCA", original=4_400_000),
        cthru("0930-0100", 2024, dept="OCA", original=6_077_671,
              account="Operation of the Office of the Child Advocate",
              dept_name="OFFICE OF THE CHILD ADVOCATE"),
        cthru("2330-0100", 2023, dept="FWE", original=9_523_813),
        cthru("2330-0100", 2024, dept="FWE", original=9_310_231, supplemental=350_000,
              account="DIV.OF MARINE FISHERIES-ADMINISTRATION",
              dept_name="DEPARTMENT OF FISH AND GAME"),
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
    # Agency / office as in exampledata.csv (EX-001, EX-004)
    assert ex1["agency_office"] == "Office of the Child Advocate"
    assert ex4["agency_office"] == "Division of Marine Fisheries"
    assert (ex1["program_purpose"], ex1["program_purpose_method"]) == (
        "Office of the child advocate", "rule",
    )
    assert (ex1["policy_area"], ex1["policy_area_method"]) == (KIDS, "department")
    assert (ex1["previously_funded"], ex1["one_time_or_recurring"]) == ("Yes", "Recurring")
    assert (ex4["policy_area"], ex4["policy_area_method"]) == (ENV, "catalog")
    assert (ex4["previously_funded"], ex4["one_time_or_recurring"]) == ("Yes", "One-time")
    assert ex4["new_or_reapprop"] == "Pending"


def test_run_reports_missing_inputs(tmp_path):
    ctx = Context(root=tmp_path, settings={"scope": {}})
    assert label.run(ctx) == 1
