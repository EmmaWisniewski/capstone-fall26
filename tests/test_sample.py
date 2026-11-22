"""The random-review sample: repeatable, covers every group, never repeats a row."""

import csv

from ma_approps import sample, schemas
from ma_approps.context import Context

SETTINGS = {"scope": {"approved_from": "2021-01-01", "approved_to": "2025-12-31"}}


def make_rows():
    rows = []
    groups = (
        ("2023", "Original appropriation", 400),
        ("2023", "Transfer", 5),
        ("2024", "Original appropriation", 300),
        ("2024", "Supplemental increase", 3),
    )
    for fy, action, n in groups:
        for i in range(n):
            rid = f"{fy}-{action[:3]}-{i}"
            rows.append({"Record ID": rid, "Fiscal year": fy, "Funding action": action})
    return rows


def test_same_seed_same_rows_new_seed_new_rows():
    rows = make_rows()
    a = sample.draw(rows, 50, seed=1)
    assert a == sample.draw(rows, 50, seed=1)
    assert a != sample.draw(rows, 50, seed=2)


def test_size_exact_no_repeats_and_every_group_covered():
    rows = make_rows()
    chosen = sample.draw(rows, 50, seed=1)
    ids = [r["Record ID"] for r in chosen]
    assert len(chosen) == 50 and len(set(ids)) == 50
    assert {(r["Fiscal year"], r["Funding action"]) for r in chosen} == {
        ("2023", "Original appropriation"), ("2023", "Transfer"),
        ("2024", "Original appropriation"), ("2024", "Supplemental increase"),
    }


def test_small_groups_get_more_than_their_share_but_not_more_than_they_have():
    sizes = {("a",): 10000, ("b",): 4}
    got = sample.shares(sizes, 100)
    assert sum(got.values()) == 100 and got[("b",)] <= 4 and got[("b",)] >= 1


def test_sample_bigger_than_file_returns_every_row():
    rows = make_rows()
    assert len(sample.draw(rows, 10_000, seed=1)) == len(rows)


def test_run_writes_file_with_review_columns(tmp_path):
    ctx = Context(output_dir=tmp_path / "out", reports_dir=tmp_path / "reports", settings=SETTINGS)
    ctx.output_dir.mkdir()
    main = ctx.output_dir / "ma_appropriations_cy2021_2025.csv"
    with open(main, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.EXPORT_COLUMNS, restval="")
        w.writeheader()
        for r in make_rows():
            w.writerow(r)
    ctx.interim_dir = tmp_path / "interim"
    ctx.interim_dir.mkdir()
    with open(ctx.interim_dir / "funding_actions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["record_id", "amount_source"])
        w.writeheader()
        for r in make_rows():
            w.writerow({"record_id": r["Record ID"], "amount_source": "cthru"})
    assert sample.run(ctx, size=20, seed=1) == 0
    with open(ctx.reports_dir / sample.SAMPLE_FILE, newline="", encoding="utf-8-sig") as f:
        out = list(csv.DictReader(f))
    assert len(out) == 20
    assert list(out[0]) == [
        *schemas.EXPORT_COLUMNS, sample.SOURCE_COLUMN, *sample.REVIEW_COLUMNS
    ]
    assert all(r["Reviewer"] == "" for r in out)
    assert all(r[sample.SOURCE_COLUMN] == "CTHRU" for r in out)


def test_missing_main_file_is_a_clear_failure(tmp_path):
    ctx = Context(output_dir=tmp_path, reports_dir=tmp_path / "r", settings=SETTINGS)
    assert sample.run(ctx) == 1
