"""validate: unread rows explained in review/unread_explanations.csv (DESIGN §7.19, §13.6; Q22)."""

import csv
import shutil

from ma_approps import schemas, validate
from ma_approps.context import Context

EXPLANATION_COLUMNS = schemas.columns("unread_explanations")


def write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def explanation(
    report="unread_sections.csv", law_key="2024-206", section="58", text="a transfer", **kw
):
    # `report` is the report's file name (PR #50, §7.19)
    row = {
        "report": report,
        "law_key": law_key,
        "section": section,
        "explanation": text,
        "explained_by": "Emily H.",
        "date": "2026-11-11",
    }
    row.update(kw)
    return row


def setup(root, tmp_path, unread=(), explanations=None, report="unread_sections"):
    """A repo copy whose reports/ holds one unread report and review/ holds the explanations."""
    shutil.copytree(root / "config", tmp_path / "config")
    columns = ["law_key", "section", "reason", "text", "explanation"]
    blank = dict.fromkeys(columns, "")
    rows = [dict(blank, law_key=k, section=s, **extra) for k, s, extra in unread]
    write(tmp_path / "reports" / f"{report}.csv", columns, rows)
    if explanations is not None:
        write(tmp_path / "review" / "unread_explanations.csv", EXPLANATION_COLUMNS, explanations)
    return Context(root=tmp_path)


def test_an_unread_row_without_an_explanation_fails(root, tmp_path):
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {})])
    assert len(validate.check_unread(ctx)) == 1


def test_a_matching_row_in_the_explanations_file_explains_it(root, tmp_path):
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {})], explanations=[explanation()])
    assert validate.check_unread(ctx) == []


def test_the_reports_own_explanation_column_still_counts(root, tmp_path):
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {"explanation": "no money"})])
    assert validate.check_unread(ctx) == []


def test_a_blank_explanation_does_not_explain_anything(root, tmp_path):
    ctx = setup(
        root, tmp_path, unread=[("2024-206", "58", {})], explanations=[explanation(text="  ")]
    )
    assert len(validate.check_unread(ctx)) == 1


def test_it_must_match_the_report_law_and_section(root, tmp_path):
    other = [
        explanation(section="59"),
        explanation(law_key="2024-207"),
        explanation(report="unread_paragraphs.csv"),
    ]
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {})], explanations=other)
    assert len(validate.check_unread(ctx)) == 1


def test_the_report_is_named_by_its_file_name_not_without_the_extension(root, tmp_path):
    ctx = setup(
        root,
        tmp_path,
        unread=[("2024-206", "58", {})],
        explanations=[explanation(report="unread_sections")],
    )
    assert len(validate.check_unread(ctx)) == 1
    assert any(p.column == "report" for _, p in validate.check_schemas(ctx))


def test_one_explanation_covers_every_paragraph_of_its_section(root, tmp_path):
    rows = [("2023-28", "3", {"reason": f"paragraph {i}"}) for i in range(3)]
    ctx = setup(
        root,
        tmp_path,
        unread=rows,
        explanations=[explanation(report="unread_paragraphs.csv", law_key="2023-28", section="3")],
        report="unread_paragraphs",
    )
    assert validate.check_unread(ctx) == []


def test_an_explanation_that_matches_nothing_is_reported_not_failed(root, tmp_path):
    ctx = setup(
        root,
        tmp_path,
        unread=[("2024-206", "58", {})],
        explanations=[explanation(), explanation(section="999", text="stale")],
    )
    assert validate.check_unread(ctx) == []
    [(_, problem)] = validate.check_orphaned_explanations(ctx)
    assert (problem.row, problem.message) == (2, "matches no unread row")


def test_nothing_is_orphaned_before_the_unread_reports_exist(root, tmp_path):
    shutil.copytree(root / "config", tmp_path / "config")
    write(tmp_path / "review" / "unread_explanations.csv", EXPLANATION_COLUMNS, [explanation()])
    assert validate.check_orphaned_explanations(Context(root=tmp_path)) == []


def test_the_explanations_file_is_checked_for_format(root, tmp_path):
    ctx = setup(
        root,
        tmp_path,
        unread=[("2024-206", "58", {})],
        explanations=[explanation(report="unread_things", explained_by="", date="soon")],
    )
    columns = {p.column for _, p in validate.check_schemas(ctx)}
    assert {"report", "explained_by", "date"} <= columns


def test_a_file_with_missing_columns_is_a_format_problem_not_a_crash(root, tmp_path):
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {})])
    write(tmp_path / "review" / "unread_explanations.csv", ["law_key", "section"], [])
    assert len(validate.check_unread(ctx)) == 1
    assert any(p.row == 0 for _, p in validate.check_schemas(ctx))


def test_run_passes_once_the_unread_rows_are_explained(root, tmp_path):
    ctx = setup(root, tmp_path, unread=[("2024-206", "58", {})], explanations=[explanation()])
    assert validate.run(ctx) == 0
    ctx = setup(root, tmp_path / "again", unread=[("2024-206", "58", {})])
    assert validate.run(ctx) == 1
