import csv

import pytest

from ma_approps import schemas


def test_export_columns_match_exampledata(root):
    with open(root / "exampledata.csv", newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert tuple(header) == schemas.EXPORT_COLUMNS


def test_policy_areas_match_policyareas_csv(root):
    with open(root / "policyareas.csv", newline="", encoding="utf-8") as f:
        areas = tuple(r["Policy area"] for r in csv.DictReader(f))
    assert areas == schemas.POLICY_AREAS
    assert "Veterans’ services" in schemas.POLICY_AREAS


def test_example_funding_action_labels():
    assert schemas.FUNDING_ACTION_LABELS["ORIG"] == "Original appropriation"
    assert schemas.FUNDING_ACTION_LABELS["INC"] == "Supplemental increase"
    assert set(schemas.FUNDING_ACTION_ADDITIVE) == set(schemas.FUNDING_ACTIONS)


@pytest.mark.parametrize(
    "args, expected",
    [
        ((2023, 28, "2", "0930-0100", "ORIG"), "2023-028-S2-0930-0100-ORIG-1"),
        ((2023, 77, "178", "2330-0100", "INC"), "2023-077-S178-2330-0100-INC-1"),
        ((2023, 15, "1", None, "INT"), "2023-015-S1-NOITEM-INT-1"),
    ],
)
def test_record_id_examples(args, expected):
    rid = schemas.assign_record_ids([schemas.record_id_prefix(*args)])[0]
    assert rid == expected
    assert schemas.RECORD_ID_RE.match(rid)


def test_record_id_ordinals_are_deterministic():
    p = schemas.record_id_prefix(2023, 28, "2", "0930-0100", "ORIG")
    q = schemas.record_id_prefix(2023, 28, "2", "0930-0101", "ORIG")
    assert schemas.assign_record_ids([p, q, p]) == [f"{p}-1", f"{q}-1", f"{p}-2"]


def test_record_id_rejects_bad_parts():
    with pytest.raises(ValueError):
        schemas.record_id_prefix(2023, 28, "2", "0930-0100", "BOGUS")
    with pytest.raises(ValueError):
        schemas.record_id_prefix(2023, 28, "2", "09300100", "ORIG")


def test_manual_rows_are_funding_actions_minus_record_id_plus_provenance():
    table = schemas.columns("funding_actions")
    assert schemas.columns("manual_rows") == [
        *table[1:],
        "source_quote",
        "entered_by",
        "entered_on",
    ]


def test_validate_rows_flags_bad_values():
    header = schemas.columns("line_item_catalog")
    row = dict.fromkeys(header, "")
    row.update(line_item="2330-0100", policy_area="Fisheries", label_every_year="yes",
               decided_on="08/09/2023")
    problems = {p.column for p in schemas.validate_rows("line_item_catalog", header, [row])}
    assert problems == {"policy_area", "label_every_year", "decided_on"}


def test_validate_rows_flags_header_order():
    header = list(reversed(schemas.columns("funds")))
    problems = schemas.validate_rows("funds", header, [])
    assert problems and problems[0].row == 0
