"""The main export file (DESIGN §7.13, §8): window, bonds, corrections, human review status."""

from ma_approps import export, schemas

SETTINGS = {"scope": {"approved_from": "2021-01-01", "approved_to": "2025-12-31"}}
LAWS = [
    {"law_key": "2023-28", "acts_year": "2023", "chapter": "28", "law_name": "FY2024 GAA"},
]


def fa(record_id, action="ORIG", event_date="2023-08-09", item="0930-0100", amount="6077671"):
    return {
        "record_id": record_id,
        "law_key": "2023-28",
        "section": "2",
        "line_item": item,
        "event_date": event_date,
        "calendar_year": event_date[:4],
        "fiscal_year": "2024",
        "funding_action": action,
        "amount": amount,
        "veto_status": "none",
        "agency_header_raw": "Office of the Child Advocate.",
        "source_url": "https://example.test/ch28",
    }


def build(rows, labels=(), catalog=(), corrections=()):
    return export.main_rows(
        list(rows), LAWS, list(labels), list(catalog), list(corrections), SETTINGS
    )


def test_columns_and_formatting():
    (row,), warnings = build([fa("2023-028-S2-0930-0100-ORIG-1")])
    assert list(row) == list(schemas.EXPORT_COLUMNS)
    assert (row["Enactment date"], row["Appropriation/change ($)"]) == ("08/09/2023", "6,077,671")
    assert row["Funding action"] == "Original appropriation"
    assert warnings == []


def test_bonds_and_dates_outside_the_window_are_left_out():
    rows, _ = build(
        [
            fa("a"),
            fa("b", action="CAP"),
            fa("c", event_date="2026-02-01"),
            fa("d", event_date="2020-12-31"),
        ]
    )
    assert [r["Record ID"] for r in rows] == ["a"]


def test_rows_are_sorted_by_record_id():
    rows, _ = build([fa("b"), fa("a")])
    assert [r["Record ID"] for r in rows] == ["a", "b"]


def test_labels_replace_placeholders():
    label = {"record_id": "a", "policy_area": "Children and families", "agency_office": "Office X"}
    (row,), _ = build([fa("a")], labels=[label])
    assert (row["Policy area"], row["Agency / office"]) == ("Children and families", "Office X")
    (row,), _ = build([fa("a")])
    assert row["Policy area"] == "Not classified"


def reviewed(label, catalog):
    (row,), _ = build([fa("a")], labels=[{"record_id": "a", **label}], catalog=catalog)
    return row["Human review status"]


def test_human_review_status_follows_who_decided_the_policy_area():
    person = [{"line_item": "0930-0100", "decided_by": "Emily R."}]
    auto = [{"line_item": "0930-0100", "decided_by": export.AUTOMATIC}]
    assert reviewed({"policy_area_method": "catalog"}, person) == "Human reviewed"
    assert reviewed({"policy_area_method": "human"}, []) == "Human reviewed"
    assert reviewed({"policy_area_method": "catalog"}, auto) == "Not human reviewed"
    assert reviewed({"policy_area_method": "department"}, person) == "Not human reviewed"
    assert reviewed({}, person) == "Not human reviewed"


def fix(field, new, old=""):
    return {"record_id": "a", "field": field, "new_value": new, "expected_old_value": old}


def test_a_correction_changes_the_cell_and_counts_as_human_reviewed():
    (row,), warnings = build([fa("a")], corrections=[fix("Program / purpose", "Fixed", "")])
    assert (row["Program / purpose"], row["Human review status"]) == ("Fixed", "Human reviewed")
    assert warnings == []


def test_a_correction_with_a_stale_expected_value_is_skipped():
    (row,), warnings = build([fa("a")], corrections=[fix("Policy area", "Education", "Housing")])
    assert (row["Policy area"], row["Human review status"]) == (
        "Not classified",
        "Not human reviewed",
    )
    assert len(warnings) == 1 and "skipped" in warnings[0]


def test_a_correction_of_an_unknown_column_is_reported():
    (row,), warnings = build([fa("a")], corrections=[fix("Nope", "x")])
    assert row["Human review status"] == "Not human reviewed"
    assert len(warnings) == 1 and "unknown column" in warnings[0]


def test_wording_changes_to_bond_items_are_left_out():
    # 2024-150 §71 rewords 1993 bond item 4000-8200: extended file only (2026-11-11)
    bond_wording = dict(fa("w", action="PURP", amount=""), section_type="capital")
    operating_wording = dict(fa("p", action="PURP", amount=""), section_type="approp_main")
    rows, _ = build([bond_wording, operating_wording])
    assert [r["Record ID"] for r in rows] == ["p"]
