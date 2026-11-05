import json
from datetime import datetime

import pytest

from ma_approps import schemas

# DESIGN §15 sample laws
SAMPLE_LAWS = (
    "2023-28",
    "2023-77",
    "2024-140",
    "2025-3",
    "2021-35",
    "2023-15",
    "2024-139",
    "2025-17",
)


@pytest.fixture
def law_list(root):
    _, rows = schemas.read_csv(root / "config" / "law_list.csv")
    return {r["law_key"]: r for r in rows}


def test_law_list_matches_schema(root):
    assert schemas.validate_file("law_list", root / "config" / "law_list.csv") == []


def test_example_law_names(law_list):
    # DESIGN §17: expected curated values
    assert law_list["2023-28"]["law_name"] == "FY2024 General Appropriations Act"
    assert (
        law_list["2023-77"]["law_name"]
        == "FY2023 Supplemental Appropriations Act (December 2023)"
    )


def test_2020_volume_laws_approved_in_2021_are_in_scope(law_list):
    for key in ("2020-358", "2020-383"):
        assert law_list[key]["acts_year"] == "2020"
        assert law_list[key]["approved_date"].startswith("2021-")
        assert law_list[key]["role"] == "in_scope"


@pytest.mark.parametrize("key", SAMPLE_LAWS)
def test_sample_matches_law_list(samples_dir, law_list, key):
    year, chapter = key.split("-")
    law = json.loads((samples_dir / "sessionlaws" / year / f"{chapter}.json").read_text("utf-8"))
    assert law["ChapterNumber"] == chapter
    assert law["ChapterText"]
    approved = datetime.strptime(law["ApprovedDate"], "%b %d %Y").date().isoformat()
    assert approved == law_list[key]["approved_date"]


# Hand-written expected read_bonds output for the two bond samples (DESIGN §11.2, §13 check 7).
# These checks only guard the expected files against typos; they don't run any reader.
BOND_SAMPLES = ("2025-17", "2024-139")


def _sample_text(samples_dir, key):
    year, chapter = key.split("-")
    law = json.loads((samples_dir / "sessionlaws" / year / f"{chapter}.json").read_text("utf-8"))
    return law["ChapterText"]


def test_expected_bond_items_appear_in_the_sample_text(samples_dir):
    _, rows = schemas.read_csv(samples_dir / "expected" / "bond_items.csv")
    assert {r["law_key"] for r in rows} == set(BOND_SAMPLES)
    for r in rows:
        text = _sample_text(samples_dir, r["law_key"])
        assert r["line_item"] in text, r["line_item"]
        assert f"${int(r['amount']):,}" in text, r["line_item"]
        assert int(r["para_start"]) <= int(r["para_end"])


def test_expected_bond_authorizations_against_item_totals(samples_dir):
    _, items = schemas.read_csv(samples_dir / "expected" / "bond_items.csv")
    _, auths = schemas.read_csv(samples_dir / "expected" / "bond_authorizations.csv")
    gaps = {}
    for a in auths:
        assert f"${int(a['authorized']):,}" in _sample_text(samples_dir, a["law_key"])
        sections = a["covers_sections"].split(";")
        total = sum(
            int(i["amount"])
            for i in items
            if i["law_key"] == a["law_key"] and i["section"] in sections
        )
        gaps[(a["law_key"], a["covers_sections"])] = total - int(a["authorized"])
    # Every borrowing section matches its items except 2024-139 §4: its §2A+§2B items total
    # $1,455,000,000 but §4 lets the state borrow only $1,055,000,000.
    assert {k: v for k, v in gaps.items() if v} == {("2024-139", "2A;2B"): 400_000_000}
