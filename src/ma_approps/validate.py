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

from ma_approps import combine, schemas
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
        ("item_number_fixes", ctx.config_dir / "item_number_fixes.csv"),
        ("corrections", ctx.review_dir / "corrections.csv"),
        ("citation_fixes", ctx.config_dir / "citation_fixes.csv"),
        ("raw_manifest", ctx.raw_dir / "manifest.csv"),
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
            if table == "item_number_fixes":
                problems += [
                    Problem(table, i, "line_item", f"not NNNN-NNNN: {r['line_item']!r}")
                    for i, r in enumerate(rows, start=1)
                    if not schemas.LINE_ITEM_RE.match(r["line_item"])
                ]
        found += [(path, p) for p in problems]
    return found


def check_unread(ctx: Context) -> list[tuple[Path, Problem]]:
    """§13.6: unread reports must be empty or every row explained (an `explanation` column)."""
    found = []
    for name in ("unread_paragraphs", "unread_paragraphs_bonds", "unread_sections"):
        path = ctx.reports_dir / f"{name}.csv"
        if not path.exists():
            continue
        _, rows = schemas.read_csv(path)
        for i, r in enumerate(rows, start=1):
            if not (r.get("explanation") or "").strip():
                found.append((path, Problem(name, i, "explanation", "unread row not explained")))
    return found


def check_amendment_amounts(ctx: Context) -> list[dict] | None:
    """§13 check 3 (workstream C): every amendment that changes an item's amount, with the item's
    running amount before and after and the struck-figure check (combine.amendment_amounts).
    None when read_amendments hasn't run. Reported only, not a failure, until Q21 and Q27 decide
    what the flagged rows mean."""
    if not (ctx.interim_dir / "amendments_raw.csv").exists():
        return None

    def rows(path: Path) -> list[dict[str, str]]:
        return schemas.read_csv(path)[1] if path.exists() else []

    inputs = {
        "items_raw": rows(ctx.interim_dir / "items_raw.csv"),
        "bond_items_raw": rows(ctx.interim_dir / "bond_items_raw.csv"),
        "manual_rows": rows(ctx.config_dir / "manual_rows.csv"),
    }
    return combine.amendment_amounts(
        combine.starting_items(inputs),
        rows(ctx.interim_dir / "amendments_raw.csv"),
        rows(ctx.config_dir / "law_list.csv"),
    )


def _read_rows(path: Path) -> list[dict[str, str]]:
    return schemas.read_csv(path)[1] if path.exists() else []


def _int(value: str | None) -> int:
    return int(value) if value not in ("", None) else 0


def _flags(row: dict[str, str]) -> set[str]:
    return {f for f in (row.get("flags") or "").split(";") if f}


# -- §13 check 4: CTHRU comparison, per fiscal year × line item ---------------------------------

CTHRU_COLUMNS = (
    "check",
    "fiscal_year",
    "line_item",
    "our_amount",
    "cthru_amount",
    "difference",
    "percent",
    "status",
    "laws",
    "note",
)
SUPPLEMENTAL_ACTIONS = ("NEW", "INC", "RED")


def _compare(
    check: str,
    ours: dict[tuple[str, str], list[dict[str, str]]],
    cthru: dict[tuple[str, str], int],
    amount_of,
) -> tuple[int, list[dict[str, str | int]]]:
    """Compare our rows with CTHRU's amount for every fiscal year × line item that has either.
    Returns (number that match, one report row for each that doesn't).

    Status of a difference: ``flagged`` (a row already carries `cthru_mismatch`), ``several_laws``
    (supplementals only: several laws touch the item, so the difference can't be attributed),
    ``missing_in_data`` (CTHRU has money and we have no row), ``not_in_cthru`` (we have money and
    CTHRU has none) or ``unexplained``."""
    matched, report = 0, []
    for key in sorted(set(ours) | set(cthru)):
        rows = ours.get(key, [])
        our_amount = sum(amount_of(r) for r in rows)
        cthru_amount = cthru.get(key, 0)
        if our_amount == cthru_amount:
            matched += 1
            continue
        laws = sorted({r["law_key"] for r in rows})
        if any("cthru_mismatch" in _flags(r) for r in rows):
            status = "flagged"
        elif check == "supplemental" and len(laws) > 1:
            status = "several_laws"
        elif not rows:
            status = "missing_in_data"
        elif not cthru_amount:
            status = "not_in_cthru"
        else:
            status = "unexplained"
        diff = our_amount - cthru_amount
        report.append(
            {
                "check": check,
                "fiscal_year": key[0],
                "line_item": key[1],
                "our_amount": our_amount,
                "cthru_amount": cthru_amount,
                "difference": diff,
                "percent": f"{diff / cthru_amount * 100:.1f}" if cthru_amount else "",
                "status": status,
                "laws": ";".join(laws),
                "note": "",
            }
        )
    return matched, report


def check_cthru(
    actions: list[dict[str, str]],
    cthru_rows: list[dict[str, str]],
    law_list: list[dict[str, str]],
) -> tuple[int, list[dict[str, str | int]]]:
    """§13 check 4 (workstream E). Only the fiscal years of an in-scope GAA are compared, so CTHRU
    years whose budget law is outside the window (FY2021) don't show as missing money.

    - ``gaa``: ORIG appropriations vs CTHRU ``original_enacted``.
    - ``supplemental``: counted NEW + INC + RED amounts vs ``supplemental``.
    - ``retained_revenue``: ORIG fee-revenue ceilings vs ``retained_revenue_ceiling``.
    §2D federal grant rows are left out: CTHRU doesn't carry them (§10). Known non-law differences
    (9C cuts) aren't annotated yet. Returns (matches, mismatch rows)."""
    orig = [
        r
        for r in actions
        if r["funding_action"] == "ORIG"
        and r["line_item"]
        and r["section_type"] != "federal_grants"
    ]
    years = {
        r["primary_fy"]
        for r in law_list
        if r["role"] == "in_scope" and r["law_type"] == "gaa" and r.get("primary_fy")
    }
    years &= {r["fiscal_year"] for r in cthru_rows}

    def group(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
        out: dict[tuple[str, str], list[dict[str, str]]] = {}
        for r in rows:
            if r["fiscal_year"] in years:
                out.setdefault((r["fiscal_year"], r["line_item"]), []).append(r)
        return out

    def theirs(column: str) -> dict[tuple[str, str], int]:
        return {
            (r["fiscal_year"], r["line_item"]): _int(r[column])
            for r in cthru_rows
            if r["fiscal_year"] in years and _int(r[column])
        }

    def amount(r: dict[str, str]) -> int:
        return _int(r["amount"])

    parts = [
        _compare(
            "gaa",
            group([r for r in orig if r["amount_kind"] == "appropriation"]),
            theirs("original_enacted"),
            amount,
        ),
        _compare(
            "supplemental",
            group(
                [
                    r
                    for r in actions
                    if r["funding_action"] in SUPPLEMENTAL_ACTIONS
                    and r["amount_kind"] in ("appropriation", "delta")  # INC and RED are deltas
                    and r["counts_toward_total"] == "true"
                    and r["line_item"]
                ]
            ),
            theirs("supplemental"),
            amount,
        ),
        _compare(
            "retained_revenue",
            group([r for r in orig if r["amount_kind"] == "retained_revenue_ceiling"]),
            theirs("retained_revenue_ceiling"),
            amount,
        ),
    ]
    return sum(m for m, _ in parts), [row for _, rows in parts for row in rows]


# -- §13 check 7: bond totals against borrowing limits -------------------------------------------

BOND_COLUMNS = (
    "law_key",
    "section",
    "bond_name",
    "authorized",
    "items_total",
    "items_count",
    "difference",
    "status",
    "line_items",
    "note",
)


def check_bond_totals(
    actions: list[dict[str, str]],
    limits: list[dict[str, str]],
    law_list: list[dict[str, str]] | None = None,
) -> tuple[int, list[dict[str, str | int]]]:
    """§13 check 7 (Q11, decided 2026-11-06): for each borrowing limit (§7.16), the total of the
    ``CAP`` items it covers (`combine.limit_for`) against what it authorizes. A difference isn't a
    reader error: it is reported, with a note naming the limit and the gap. A ``CAP`` item that no
    limit covers is reported too (``no_limit``). Restated items (other laws' ``CAP`` rows) aren't
    part of a limit. With ``law_list``, limits of laws that aren't ``in_scope`` are skipped: their
    items are left out of the data on purpose, so they could never match. Returns (limits that
    match, report rows)."""
    if law_list is not None:
        in_scope = {r["law_key"] for r in law_list if r["role"] == "in_scope"}
        limits = [lim for lim in limits if lim["law_key"] in in_scope]
    bond = [
        r
        for r in actions
        if r["funding_action"] == "CAP" and r["law_key"] == r["target_law_key"] and r["line_item"]
    ]
    covered: dict[int, list[dict[str, str]]] = {id(lim): [] for lim in limits}
    report: list[dict[str, str | int]] = []
    for r in bond:
        lim = combine.limit_for(r, limits)
        if lim is not None:
            covered[id(lim)].append(r)
        else:
            report.append(
                {
                    "law_key": r["law_key"],
                    "section": r["section"],
                    "bond_name": "",
                    "authorized": "",
                    "items_total": _int(r["amount"]),
                    "items_count": 1,
                    "difference": "",
                    "status": "no_limit",
                    "line_items": r["line_item"],
                    "note": f"{r['line_item']} in {r['law_key']} §{r['section']} has no "
                    "borrowing limit (bond_authorizations_raw)",
                }
            )
    matched = 0
    for lim in limits:
        rows = covered[id(lim)]
        total = sum(_int(r["amount"]) for r in rows)
        authorized = _int(lim["authorized"])
        if total == authorized:
            matched += 1
            continue
        gap = total - authorized
        name = lim["bond_name"] or "borrowing limit"
        report.append(
            {
                "law_key": lim["law_key"],
                "section": lim["section"],
                "bond_name": lim["bond_name"],
                "authorized": authorized,
                "items_total": total,
                "items_count": len(rows),
                "difference": gap,
                "status": "no_items" if not rows else "differs",
                "line_items": ";".join(r["line_item"] for r in rows),
                "note": f"{name} ({lim['law_key']} §{lim['section']}): items add ${total:,} "
                f"against ${authorized:,} authorized, a gap of ${gap:,}",
            }
        )
    return matched, report


def _write_report(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(columns), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


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
    amounts = check_amendment_amounts(ctx)
    if amounts is not None:
        path = out / "amendment_amounts.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=combine.AMOUNT_COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows({k: "" if v is None else v for k, v in r.items()} for r in amounts)
        review = sum(r["review"] == "true" for r in amounts)
        print(
            f"  amendment amounts: {len(amounts)} changes, {review} to review in {path.name}"
            " (reported, not yet a failure: Q21, Q27)"
        )
    actions = _read_rows(ctx.interim_dir / "funding_actions.csv")
    cthru_rows = _read_rows(ctx.interim_dir / "cthru_line_items.csv")
    if actions and cthru_rows:
        law_list = _read_rows(ctx.config_dir / "law_list.csv")
        matched, mismatches = check_cthru(actions, cthru_rows, law_list)
        _write_report(out / "cthru_mismatches.csv", CTHRU_COLUMNS, mismatches)
        unexplained = sum(m["status"] in ("unexplained", "missing_in_data", "not_in_cthru")
                          for m in mismatches)
        print(
            f"  CTHRU comparison: {matched} match, {len(mismatches)} differ "
            f"({unexplained} unexplained) in cthru_mismatches.csv (reported, not a failure)"
        )
    limits = _read_rows(ctx.interim_dir / "bond_authorizations_raw.csv")
    if actions and limits:
        law_list = _read_rows(ctx.config_dir / "law_list.csv")
        matched, gaps = check_bond_totals(actions, limits, law_list)
        in_scope_limits = sum(
            lim["law_key"] in {r["law_key"] for r in law_list if r["role"] == "in_scope"}
            for lim in limits
        )
        _write_report(out / "bond_totals.csv", BOND_COLUMNS, gaps)
        print(
            f"  bond totals: {matched} of {in_scope_limits} in-scope limits match their items, "
            f"{len(gaps)} reported in bond_totals.csv (reported, not a failure: Q11)"
        )
    return 1 if schema_problems or unread else 0
