"""`validate`: the validation suite (DESIGN §13). Owner: workstream E.

M0 implements check 1 (file formats and allowed values) and the coverage check on the
``unread_*`` reports. The remaining checks land with their milestones:
example rows (M1), CTHRU comparison (M2/M3), struck-figure (M3), bond totals (M4),
law status and orphaned corrections (M5).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from ma_approps import schemas
from ma_approps.context import Context
from ma_approps.schemas import Problem

IMPLEMENTED = True

PROBLEM_COLUMNS = ("table", "path", "row", "column", "message")


def _files(ctx: Context) -> list[tuple[str, Path]]:
    """Every fixed-format file that may exist, as (schema name, path)."""
    interim = ctx.interim_dir
    return [
        ("law_list", ctx.config_dir / "law_list.csv"),
        ("manual_rows", ctx.config_dir / "manual_rows.csv"),
        ("funds", ctx.config_dir / "funds.csv"),
        ("line_item_catalog", ctx.config_dir / "line_item_catalog.csv"),
        ("department_policy_areas", ctx.config_dir / "department_policy_areas.csv"),
        ("corrections", ctx.review_dir / "corrections.csv"),
        *(
            (name, interim / f"{name}.csv")
            for name in (
                "items_raw",
                "bond_items_raw",
                "amendments_raw",
                "cthru_line_items",
                "funding_actions",
                "fund_splits",
                "running_amounts",
                "labels",
            )
        ),
    ]


def check_law_list(rows: list[dict[str, str]], scope: dict) -> list[Problem]:
    lo = date.fromisoformat(scope["approved_from"])
    hi = date.fromisoformat(scope["approved_to"])
    problems = []
    seen: set[str] = set()
    for i, r in enumerate(rows, start=1):
        key = r["law_key"]
        if key in seen:
            problems.append(Problem("law_list", i, "law_key", f"duplicate {key}"))
        seen.add(key)
        if r["acts_year"] and r["chapter"] and key != schemas.law_key(r["acts_year"], r["chapter"]):
            problems.append(Problem("law_list", i, "law_key", "≠ {acts_year}-{chapter}"))
        try:
            approved = date.fromisoformat(r["approved_date"])
        except ValueError:
            continue  # already reported by the schema check
        in_window = lo <= approved <= hi
        if r["role"] == "in_scope" and not in_window:
            problems.append(
                Problem("law_list", i, "role", "in_scope but approved outside window")
            )
        if r["role"] == "reference_only" and in_window:
            problems.append(
                Problem("law_list", i, "role", "reference_only but approved inside window")
            )
    return problems


def check_record_ids(table: str, rows: list[dict[str, str]]) -> list[Problem]:
    problems = []
    seen: set[str] = set()
    for i, r in enumerate(rows, start=1):
        rid = r.get("record_id", "")
        if rid and not schemas.RECORD_ID_RE.match(rid):
            problems.append(Problem(table, i, "record_id", f"malformed {rid!r} (§9.6)"))
        if rid in seen:
            problems.append(Problem(table, i, "record_id", f"duplicate {rid!r}"))
        seen.add(rid)
    return problems


def check_schemas(ctx: Context) -> list[tuple[Path, Problem]]:
    found = []
    for table, path in _files(ctx):
        if not path.exists():
            continue
        header, rows = schemas.read_csv(path)
        problems = schemas.validate_rows(table, header, rows)
        if not any(p.row == 0 for p in problems):
            if table == "law_list":
                problems += check_law_list(rows, ctx.settings["scope"])
            if table == "funding_actions":
                problems += check_record_ids(table, rows)
        found += [(path, p) for p in problems]
    return found


def check_unread(ctx: Context) -> list[tuple[Path, Problem]]:
    """§13.6: unread reports must be empty or every row explained (an `explanation` column)."""
    found = []
    for name in ("unread_paragraphs", "unread_sections"):
        path = ctx.reports_dir / f"{name}.csv"
        if not path.exists():
            continue
        _, rows = schemas.read_csv(path)
        for i, r in enumerate(rows, start=1):
            if not (r.get("explanation") or "").strip():
                found.append((path, Problem(name, i, "explanation", "unread row not explained")))
    return found


def write_problems(path: Path, problems: list[tuple[Path, Problem]], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(PROBLEM_COLUMNS)
        for p_path, p in problems:
            rel = p_path.relative_to(root) if p_path.is_relative_to(root) else p_path
            w.writerow((p.table, rel.as_posix(), p.row, p.column, p.message))


def run(ctx: Context) -> int:
    out = ctx.reports_dir / "validation"
    schema_problems = check_schemas(ctx)
    unread = check_unread(ctx)
    write_problems(out / "schema_problems.csv", schema_problems, ctx.root)
    write_problems(out / "unread_unexplained.csv", unread, ctx.root)
    for path, p in schema_problems + unread:
        print(f"  {path.name}:{p.row} {p.column}: {p.message}")
    print(
        f"  schema problems: {len(schema_problems)}; unexplained unread rows: {len(unread)}"
    )
    return 1 if schema_problems or unread else 0
