"""Golden test (DESIGN §17, M1): parser- and assemble-derived fields for EX-001…EX-004.

Runs the pipeline offline on tests/fixtures (law texts plus a CTHRU snapshot) and compares against
tests/fixtures/expected/golden.csv. Skipped until the M1 stages exist.
"""

import pytest

from ma_approps import cli, schemas
from ma_approps.context import Context

M1_STAGES = ("cthru", "read_items", "read_amendments", "assemble", "export")
CHECKED = (
    "Law citation",
    "Enactment date",
    "Calendar year",
    "Fiscal year",
    "Section",
    "Line item",
    "Funding action",
    "Appropriation/change ($)",
    "Source URL",
)


def test_golden(root, fixtures_dir, tmp_path):
    missing = [s for s in M1_STAGES if not getattr(cli.stage_module(s), "IMPLEMENTED", False)]
    if missing:
        pytest.skip(f"M1 stages not implemented: {', '.join(missing)}")

    ctx = Context(
        root=root,
        raw_dir=fixtures_dir,
        interim_dir=tmp_path / "interim",
        output_dir=tmp_path / "output",
        reports_dir=tmp_path / "reports",
        offline=True,
    )
    stages = [*M1_STAGES]
    describe_done = getattr(cli.stage_module("describe"), "IMPLEMENTED", False)
    if describe_done:
        stages.append("describe")
    assert cli.run_stages(ctx, stages) == 0

    _, exported = schemas.read_csv(ctx.output_dir / "ma_appropriations_cy2021_2025.csv")
    _, golden = schemas.read_csv(fixtures_dir / "expected" / "golden.csv")
    fields = (*CHECKED, "Agency / office") if describe_done else CHECKED
    for g in golden:
        matches = [
            r
            for r in exported
            if (r["Law citation"], r["Section"], r["Line item"])
            == (g["Law citation"], g["Section"], g["Line item"])
        ]
        assert len(matches) == 1, f"{g['Example']}: {len(matches)} matching rows"
        got = {f: matches[0][f] for f in fields}
        assert got == {f: g[f] for f in fields}, g["Example"]
