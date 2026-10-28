import json
from datetime import datetime

import pytest

from ma_approps import schemas

# DESIGN §15 sample laws
SAMPLE_LAWS = ("2023-28", "2023-77", "2024-140", "2025-3", "2021-35", "2023-15")


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
