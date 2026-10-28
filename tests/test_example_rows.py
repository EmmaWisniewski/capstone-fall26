"""Example-rows test (DESIGN §17, M1): parser- and combine-derived fields for EX-001…EX-004.

Runs the pipeline offline on tests/samples (law texts plus a CTHRU snapshot) and compares against
tests/samples/expected/example_rows.csv. Skipped until the M1 stages exist.
"""

import pytest

from ma_approps import cli, schemas
from ma_approps.context import Context

M1_STAGES = ("cthru", "read_items", "read_amendments", "combine", "export")
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


def test_example_rows(root, samples_dir, tmp_path):
    missing = [s for s in M1_STAGES if not getattr(cli.stage_module(s), "IMPLEMENTED", False)]
    if missing:
        pytest.skip(f"M1 stages not implemented: {', '.join(missing)}")

    ctx = Context(
        root=root,
        raw_dir=samples_dir,
        interim_dir=tmp_path / "interim",
        output_dir=tmp_path / "output",
        reports_dir=tmp_path / "reports",
        offline=True,
    )
    stages = [*M1_STAGES]
    label_done = getattr(cli.stage_module("label"), "IMPLEMENTED", False)
    if label_done:
        stages.append("label")
    assert cli.run_stages(ctx, stages) == 0

    _, exported = schemas.read_csv(ctx.output_dir / "ma_appropriations_cy2021_2025.csv")
    _, expected = schemas.read_csv(samples_dir / "expected" / "example_rows.csv")
    fields = (*CHECKED, "Agency / office") if label_done else CHECKED
    for g in expected:
        matches = [
            r
            for r in exported
            if (r["Law citation"], r["Section"], r["Line item"])
            == (g["Law citation"], g["Section"], g["Line item"])
        ]
        assert len(matches) == 1, f"{g['Example']}: {len(matches)} matching rows"
        got = {f: matches[0][f] for f in fields}
        assert got == {f: g[f] for f in fields}, g["Example"]
