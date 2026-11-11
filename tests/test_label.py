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


EOTSS = "EXECUTIVE OFFICE OF TECHNOLOGY SERVICES AND SECURITY"


def test_vague_bond_heading_uses_the_secretariat():
    assert label.header_agency("Office of the Secretary", EOTSS) == (
        "Executive Office of Technology Services and Security"
    )
    assert label.header_agency("Department of Revenue", EOTSS) == "Department of Revenue"
    assert label.header_agency("Office of the Secretary") == "Office of the Secretary"
    assert label.header_agency(
        "Highway Division", "MASSACHUSETTS DEPARTMENT OF TRANSPORTATION"
    ) == "Massachusetts Department of Transportation Highway Division"
    assert label.header_agency("Division of Banks", EOTSS) == "Division of Banks"
    # Through label_rows: the secretariat comes from bond_items_raw (2024-139 §2A)
    row = dict(action("2024-139-S2A-1790-3014-CAP-1", "1790-3014", 2025, "CAP", 750_000_000,
                      header="Office of the Secretary"), law_key="2024-139", section="2A")
    item = dict.fromkeys(schemas.columns("bond_items_raw"), "")
    item.update(law_key="2024-139", section="2A", line_item="1790-3014",
                secretariat_header_raw=EOTSS)
    [out] = label.label_rows([row], [], [], [], [item])
    assert out["agency_office"] == "Executive Office of Technology Services and Security"


def test_heading_only_offices_use_the_all_caps_heading():
    # No office line under the heading (2022-175 items 0330-6000…, 2022-140 item 0640-1005)
    assert label.header_agency("", "JUDICIARY") == "Judiciary"
    assert label.header_agency("", "TREASURER AND RECEIVER GENERAL") == (
        "Treasurer and Receiver General"
    )


def test_inherited_heading_from_another_department_is_replaced():
    # 2022-140 §2: 7066-2011 and 8000-2028 sit under "The Department of Children and Families"
    cthru_rows = [
        cthru("4800-0038", 2024, account="x", dept_name="DEPARTMENT OF CHILDREN AND FAMILIES"),
        cthru("7066-0000", 2024, account="x", dept_name="DEPARTMENT OF HIGHER EDUCATION"),
        cthru("8910-0102", 2024, account="x", dept_name="SHERIFF DEPARTMENT HAMPDEN"),
        cthru("8910-8800", 2024, account="x", dept_name="SHERIFF DEPARTMENT SUFFOLK"),
    ]
    depts = label.Departments(cthru_rows)
    dcf = "The Department of Children and Families"
    assert label.agency_office(action("a", "7066-2011", 2023, "CAP", header=dcf), None, "",
                               depts) == "Department of Higher Education"
    assert label.agency_office(action("b", "4800-0017", 2023, "CAP", header=dcf), None, "",
                               depts) == "Department of Children and Families"
    # A department that uses the prefix keeps its own heading, even if another one uses it more
    assert label.agency_office(action("c", "8910-0001", 2023, "CAP",
                                      header="SHERIFF DEPARTMENT SUFFOLK"), None, "",
                               depts) == "Suffolk Sheriff's Department"


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


def test_amendment_rows_take_the_line_s_own_purpose_and_department():
    amend = "SECTION 75. Item 7008-1116 of section 2 of chapter 41 of the acts of 2019 is amended"
    rows = [
        action("2021-024-S2-7008-1116-ORIG-1", "7008-1116", 2022,
               text="For the operation of the office of travel and tourism; provided, that"),
        action("2021-024-S75-7008-1116-REAUTH-1", "7008-1116", 2022, "REAUTH", 0, text=amend),
        action("2023-077-S9-9999-0001-REAUTH-1", "9999-0001", 2024, "REAUTH", 0,
               text="SECTION 9. Said item 9999-0001 is hereby amended"),
    ]
    cthru_rows = [cthru("7008-1116", 2020, dept="MMP", account="Mass Office of Travel",
                        dept_name="MASSACHUSETTS MARKETING PARTNERSHIP")]
    out = {r["record_id"]: r for r in label.label_rows(rows, cthru_rows, [], [])}
    reauth = out["2021-024-S75-7008-1116-REAUTH-1"]
    assert reauth["program_purpose"] == "Office of travel and tourism"  # not "SECTION 75. …"
    assert reauth["agency_office"] == "Office of Travel and Tourism"
    # Nothing known about the line: blank rather than the amending section's wording
    assert out["2023-077-S9-9999-0001-REAUTH-1"]["program_purpose"] == ""


def test_printed_names_match_cthru_names_loosely():
    assert label.name_key("Department of Elementary and Secondary Education") == label.name_key(
        "DEPARTMENT OF ELEMENTARY & SECONDARY EDUCATION")
    assert label.name_key("Massachusetts Emergency Management Agency") == label.name_key(
        "EMERGENCY MANAGEMENT AGENCY")
    # A federal grant line CTHRU doesn't list: the agency is tried before the secretariat
    cthru_rows = [cthru("4510-0100", 2024, dept="DPH", account="x",
                        dept_name="DEPARTMENT OF PUBLIC HEALTH"),
                  cthru("4000-0300", 2024, dept="EHS", account="x",
                        dept_name="EXECUTIVE OFFICE OF HEALTH and HUMAN SERVICES")]
    depts = label.Departments(cthru_rows)
    assert depts.department_code("4570-1010", 2025, (
        "Department of Public Health", "Executive Office of Health and Human Services")) == "DPH"


def test_new_or_reapprop_follows_the_group_rule():
    expected = {
        "ORIG": "New", "NEW": "New", "INC": "New", "RED": "New", "CAP": "New",
        "REAUTH": "Re-appropriation", "PAC": "Re-appropriation",
        "XFER": "Transfer of existing authority", "PURP": "Transfer of existing authority",
        "INT": "Pending",
    }
    for funding_action, answer in expected.items():
        assert label.new_or_reapprop(action("a", "1234-5678", 2024, funding_action)) == answer


def test_rows_with_no_line_item_get_an_area_by_funding_action():
    # D decided 2026-11-11: fund transfers -> Debt service; interim budgets -> Multiple
    rows = [
        action("x", "", 2024, "XFER", text="transfer to the Stabilization Fund"),
        action("i", "", 2024, "INT", text="interim budget"),
        action("n", "", 2024, "NEW", text="for a program"),
    ]
    out = {r["record_id"]: r for r in label.label_rows(rows, [], [], [])}
    assert (out["x"]["policy_area"], out["x"]["policy_area_method"]) == (
        "Debt service, reserves, and statewide finance", "rule")
    assert (out["i"]["policy_area"], out["i"]["policy_area_method"]) == ("Multiple", "rule")
    assert (out["n"]["policy_area"], out["n"]["policy_area_method"]) == ("", "")
    assert not schemas.validate_rows("labels", schemas.columns("labels"), list(out.values()))


def test_bond_lines_get_their_department_area_from_the_line_number():
    # Bond items aren't in CTHRU; their first four digits point to a department
    cthru_rows = [
        cthru("7066-0000", 2024, dept="RGT", account="x"),
        cthru("1599-0026", 2024, dept="ANF", account="x"),
        cthru("4000-0300", 2022, dept="EHS", account="x"),
    ]
    rows = {(r["line_item"], int(r["fiscal_year"])): r for r in cthru_rows}
    depts = label.Departments(cthru_rows)
    departments = {
        "RGT": {"department_code": "RGT", "policy_area": "Education", "mixed": "false"},
        "ANF": {"department_code": "ANF", "policy_area": "", "mixed": "true"},
        "EHS": {"department_code": "EHS", "policy_area": "Health and public health",
                "mixed": "false"},
    }
    assert label.policy_area("7066-2011", 2023, {}, departments, rows, depts) == (
        "Education", "department",
    )
    # A mixed department (A&F reserves) still goes to review
    assert label.policy_area("1599-1953", 2025, {}, departments, rows, depts) == ("", "")
    # A line CTHRU lists in another year uses that year's department
    assert label.policy_area("4000-0300", 2025, {}, departments, rows, depts) == (
        "Health and public health", "department",
    )
    # No CTHRU line with these digits at all: review
    assert label.policy_area("6121-2617", 2025, {}, departments, rows, depts) == ("", "")


def test_mass_dot_capital_lines_use_the_printed_department():
    # MassDOT's capital lines (6121-…) never appear in CTHRU, but the law prints its name
    cthru_rows = [cthru("1595-6368", 2024, dept="DOT", account="x",
                        dept_name="MASSACHUSETTS DEPARTMENT OF TRANSPORTATION")]
    rows = {(r["line_item"], int(r["fiscal_year"])): r for r in cthru_rows}
    departments = {"DOT": {"department_code": "DOT", "policy_area": "Transportation",
                           "mixed": "false"}}
    printed = ("Massachusetts Department of Transportation",
               "Massachusetts Department of Transportation Highway Division")
    assert label.policy_area("6121-2617", 2025, {}, departments, rows,
                             label.Departments(cthru_rows), printed) == ("Transportation",
                                                                         "department")


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
    assert ex4["new_or_reapprop"] == "New"  # a supplemental increase (Q3)


def test_run_reports_missing_inputs_and_carries_on(tmp_path, capsys):
    ctx = Context(root=tmp_path, settings={"scope": {}})
    assert label.run(ctx) == 0
    assert "funding_actions.csv is missing (run the combine stage first)" in capsys.readouterr().out
    assert schemas.validate_file("labels", tmp_path / "data" / "interim" / "labels.csv") == []
