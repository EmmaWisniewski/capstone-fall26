"""The codebook names every column of the published files (Decision Log, 2026-11-18).

Written by hand for readability; this test fails when a column is added or renamed in schemas.py
without the codebook being updated in the same change.
"""

from pathlib import Path

import pytest

from ma_approps import schemas

CODEBOOK = Path(__file__).resolve().parents[1] / "docs" / "CODEBOOK.md"
COLUMNS = sorted(
    {*schemas.EXPORT_COLUMNS, *schemas.CAPITAL_EXPORT_COLUMNS, *schemas.SUMMARY_COLUMNS}
)


@pytest.mark.parametrize("column", COLUMNS)
def test_every_published_column_is_in_the_codebook(column):
    assert f"**{column}**" in CODEBOOK.read_text(encoding="utf-8"), (
        f"docs/CODEBOOK.md doesn't describe the column {column!r} (write it in bold)"
    )


@pytest.mark.parametrize("area", schemas.POLICY_AREAS)
def test_every_policy_area_is_in_the_codebook(area):
    assert area in CODEBOOK.read_text(encoding="utf-8")
