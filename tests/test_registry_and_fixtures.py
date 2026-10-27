import json
from datetime import datetime

import pytest

from ma_approps import schemas

# DESIGN §15 fixture laws
FIXTURE_LAWS = ("2023-28", "2023-77", "2024-140", "2025-3", "2021-35", "2023-15")


@pytest.fixture
def registry(root):
    _, rows = schemas.read_csv(root / "config" / "laws_registry.csv")
    return {r["law_key"]: r for r in rows}


def test_registry_matches_schema(root):
    assert schemas.validate_file("laws_registry", root / "config" / "laws_registry.csv") == []


def test_golden_law_names(registry):
    # DESIGN §17: expected curated values
    assert registry["2023-28"]["law_name"] == "FY2024 General Appropriations Act"
    assert (
        registry["2023-77"]["law_name"]
        == "FY2023 Supplemental Appropriations Act (December 2023)"
    )


def test_2020_volume_laws_approved_in_2021_are_in_scope(registry):
    for key in ("2020-358", "2020-383"):
        assert registry[key]["acts_year"] == "2020"
        assert registry[key]["approved_date"].startswith("2021-")
        assert registry[key]["role"] == "in_scope"


@pytest.mark.parametrize("key", FIXTURE_LAWS)
def test_fixture_matches_registry(fixtures_dir, registry, key):
    year, chapter = key.split("-")
    law = json.loads((fixtures_dir / "sessionlaws" / year / f"{chapter}.json").read_text("utf-8"))
    assert law["ChapterNumber"] == chapter
    assert law["ChapterText"]
    approved = datetime.strptime(law["ApprovedDate"], "%b %d %Y").date().isoformat()
    assert approved == registry[key]["approved_date"]
