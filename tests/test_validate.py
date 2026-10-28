import shutil

from ma_approps import cli, schemas, validate
from ma_approps.context import Context


def test_validate_passes_on_repo(root, tmp_path):
    ctx = Context(root=root, reports_dir=tmp_path / "reports")
    assert validate.run(ctx) == 0
    assert (tmp_path / "reports" / "validation" / "schema_problems.csv").exists()


def test_validate_catches_registry_role_outside_window(root, tmp_path):
    for d in ("config", "review"):
        shutil.copytree(root / d, tmp_path / d)
    path = tmp_path / "config" / "laws_registry.csv"
    old, new = "2026-55,2026,55,2026-04-06", "2026-55,2026,55,2025-04-06"
    text = path.read_text("utf-8").replace(old, new)
    path.write_text(text, "utf-8")
    ctx = Context(root=tmp_path)
    problems = [p for _, p in validate.check_schemas(ctx)]
    assert any(p.column == "role" and "reference_only" in p.message for p in problems)


def test_validate_catches_bad_ledger_record_id(root, tmp_path):
    shutil.copytree(root / "config", tmp_path / "config")
    (tmp_path / "data" / "interim").mkdir(parents=True)
    header = schemas.columns("ledger")
    row = dict.fromkeys(header, "")
    row.update(
        record_id="EX-001", law_key="2023-28", section="2", line_item="0930-0100",
        target_law_key="2023-28", event_date="2023-08-09", calendar_year="2023",
        fiscal_year="2024", fy_rule="stated", section_type="approp_main",
        funding_action="ORIG", amount_kind="appropriation", amount="6077671", amount_source="cthru",
        additive="true",
    )
    with open(tmp_path / "data" / "interim" / "ledger.csv", "w", encoding="utf-8") as f:
        f.write(",".join(header) + "\n" + ",".join(row[c] for c in header) + "\n")
    problems = [p for _, p in validate.check_schemas(Context(root=tmp_path))]
    assert [p.column for p in problems] == ["record_id"]


def test_empty_pipeline_runs(root, tmp_path):
    # M0: every stub stage is skipped and validate passes
    ctx = Context(root=root, reports_dir=tmp_path / "reports", interim_dir=tmp_path / "interim")
    assert cli.run_stages(ctx, list(cli.STAGE_NAMES)) == 0
