"""`validate`: the validation suite (DESIGN §13). Owner: workstream E.

Implemented: check 1 (file formats and allowed values), the coverage check on the ``unread_*``
reports (a row is explained in the report's own column or in review/unread_explanations.csv,
§7.19, Q22), check 3 (struck figures), check 4 (CTHRU comparison) and check 7 (bond totals).
Check 8 (law status) writes reports/law_status.csv, whose note the export repeats in its last
column. Checks 3, 4 and 7 are reported, not failures. Still to come: orphaned corrections (M5).
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
        ("unread_explanations", ctx.review_dir / "unread_explanations.csv"),
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


def _explanations(ctx: Context) -> tuple[Path, list[dict[str, str]]]:
    """``review/unread_explanations.csv`` (§7.19, Q22): where a person says why an unread row needs
    no code. The reports themselves are generated and are never hand-edited."""
    path = ctx.review_dir / "unread_explanations.csv"
    return path, (schemas.read_csv(path)[1] if path.exists() else [])


def check_unread(ctx: Context) -> list[tuple[Path, Problem]]:
    """§13.6: unread reports must be empty or every row explained.

    A row is explained by its own `explanation` column or by a row of
    ``review/unread_explanations.csv`` with the same report (its file name, e.g.
    ``unread_sections.csv``, as PR #50 decided), law and section and a written explanation. One
    explanation covers every row of that section, which is what a paragraph report needs.
    """
    _, explanations = _explanations(ctx)
    explained = {
        (e.get("report", ""), e.get("law_key", ""), e.get("section", ""))
        for e in explanations
        if (e.get("explanation") or "").strip()
    }
    found = []
    for name in schemas.UNREAD_REPORTS:  # file names, e.g. "unread_sections.csv"
        path = ctx.reports_dir / name
        if not path.exists():
            continue
        _, rows = schemas.read_csv(path)
        for i, r in enumerate(rows, start=1):
            if (r.get("explanation") or "").strip():
                continue
            if (name, r.get("law_key", ""), r.get("section", "")) in explained:
                continue
            table = name.removesuffix(".csv")
            found.append((path, Problem(table, i, "explanation", "unread row not explained")))
    return found


def check_orphaned_explanations(ctx: Context) -> list[tuple[Path, Problem]]:
    """An explanation that matches no unread row, for example after a reader fix removed the row.
    Reported, not a failure. Nothing is reported while the unread reports haven't been written,
    because a missing report says nothing about the explanations."""
    path, explanations = _explanations(ctx)
    keys: set[tuple[str, str, str]] = set()
    any_report = False
    for name in schemas.UNREAD_REPORTS:
        report = ctx.reports_dir / name
        if report.exists():
            any_report = True
            keys |= {
                (name, r.get("law_key", ""), r.get("section", ""))
                for r in schemas.read_csv(report)[1]
            }
    if not any_report:
        return []
    return [
        (path, Problem("unread_explanations", i, "section", "matches no unread row"))
        for i, e in enumerate(explanations, start=1)
        if (e.get("report", ""), e.get("law_key", ""), e.get("section", "")) not in keys
    ]


def check_amendment_amounts(ctx: Context) -> list[dict] | None:
    """§13 check 3 (workstream C): every amendment that changes an item's amount, with the item's
    running amount before and after and the struck-figure check (combine.amendment_amounts).
    None when read_amendments hasn't run. Reported, not a failure: Q21 and Q27 (decided 2026-11-11)
    send every flagged change to a person."""
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
    partial_years: frozenset[str] = frozenset(),
    matches: list[dict[str, str]] | None = None,
) -> tuple[int, list[dict[str, str | int]]]:
    """Compare our rows with CTHRU's amount for every fiscal year × line item that has either.
    Returns (number that match, one report row for each that doesn't).

    Status of a difference: ``flagged`` (a row already carries `cthru_mismatch`),
    ``earlier_laws`` (a year in ``partial_years``, where CTHRU's total also holds laws approved
    before the window, and ours is below it), ``missing_in_data`` (CTHRU has money and we have no
    row), ``not_in_cthru`` (we have money and CTHRU has none) or ``unexplained``. Several laws
    touching one item isn't an explanation: CTHRU's figure is the total of all of them.
    With ``matches``, each item that matches is appended to it (check, year, item, laws), for the
    law status (check 8)."""
    matched, report = 0, []
    for key in sorted(set(ours) | set(cthru)):
        rows = ours.get(key, [])
        our_amount = sum(amount_of(r) for r in rows)
        cthru_amount = cthru.get(key, 0)
        if our_amount == cthru_amount:
            matched += 1
            if matches is not None:
                laws = ";".join(sorted({r["law_key"] for r in rows}))
                matches.append(
                    {"check": check, "fiscal_year": key[0], "line_item": key[1], "laws": laws}
                )
            continue
        laws = sorted({r["law_key"] for r in rows})
        if any("cthru_mismatch" in _flags(r) for r in rows):
            status = "flagged"
        elif key[0] in partial_years and our_amount < cthru_amount:
            status = "earlier_laws"
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
    matches: list[dict[str, str]] | None = None,
) -> tuple[int, list[dict[str, str | int]]]:
    """§13 check 4 (workstream E). The fiscal years of an in-scope GAA are compared in full. A
    year whose budget law is outside the window (FY2021) isn't, so it doesn't show as missing
    money, but its supplemental items are: laws approved in 2021 still change FY2021 items. There
    only the items we have rows for are compared, and a shortfall is ``earlier_laws``, because
    CTHRU's total also holds supplementals approved before 2021.

    - ``gaa``: ORIG appropriations vs CTHRU ``original_enacted``.
    - ``supplemental``: NEW + INC + RED amounts vs ``supplemental``. Every row counts, whether or
      not it counts toward the operating total: CTHRU carries federal and ARPA money too.
    - ``retained_revenue``: fee-revenue ceilings vs ``retained_revenue_ceiling``. CTHRU shows §2B
      chargebacks only as ceilings, so those rows go here, not to ``gaa``. A same-year increase
      to such an item (a supplement, or an amendment of the GAA's figure) is added to its
      ceiling, because CTHRU folds it in (8100-0102 FY2024: $45M printed + $7M = $52M).
    §2D federal grant rows are left out: CTHRU doesn't carry them (§10). Known non-law differences
    (9C cuts) aren't annotated yet. Returns (matches, mismatch rows)."""
    orig = [
        r
        for r in actions
        if r["funding_action"] == "ORIG"
        and r["line_item"]
        and r["section_type"] != "federal_grants"
    ]
    deltas = [
        r
        for r in actions
        if r["funding_action"] in SUPPLEMENTAL_ACTIONS
        and r["amount_kind"] in ("appropriation", "delta")  # INC and RED are deltas
        and r["line_item"]
        and r["section_type"] != "federal_grants"
    ]

    def is_ceiling(r: dict[str, str]) -> bool:
        return r["amount_kind"] == "retained_revenue_ceiling" or r["section_type"] == "isf"

    ceiling_keys = {(r["fiscal_year"], r["line_item"]) for r in orig if is_ceiling(r)}
    ceiling_keys |= {
        (r["fiscal_year"], r["line_item"]) for r in deltas if r["section_type"] == "isf"
    }
    years = {
        r["primary_fy"]
        for r in law_list
        if r["role"] == "in_scope" and r["law_type"] == "gaa" and r.get("primary_fy")
    }
    cthru_years = {r["fiscal_year"] for r in cthru_rows}
    years &= cthru_years

    def group(
        rows: list[dict[str, str]], yrs: set[str] = years
    ) -> dict[tuple[str, str], list[dict[str, str]]]:
        out: dict[tuple[str, str], list[dict[str, str]]] = {}
        for r in rows:
            if r["fiscal_year"] in yrs:
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

    def in_ceiling_group(r: dict[str, str]) -> bool:
        return (r["fiscal_year"], r["line_item"]) in ceiling_keys

    supplemental = [r for r in deltas if not in_ceiling_group(r)]
    partial = {r["fiscal_year"] for r in supplemental} & (cthru_years - years)
    ours_partial = group(supplemental, partial)
    theirs_partial = {
        (r["fiscal_year"], r["line_item"]): _int(r["supplemental"])
        for r in cthru_rows
        if (r["fiscal_year"], r["line_item"]) in ours_partial and _int(r["supplemental"])
    }

    parts = [
        _compare(
            "gaa",
            group([r for r in orig if r["amount_kind"] == "appropriation" and not is_ceiling(r)]),
            theirs("original_enacted"),
            amount,
            matches=matches,
        ),
        _compare(
            "supplemental",
            group(supplemental) | ours_partial,
            theirs("supplemental") | theirs_partial,
            amount,
            frozenset(partial),
            matches,
        ),
        _compare(
            "retained_revenue",
            group([r for r in orig if is_ceiling(r)] + [r for r in deltas if in_ceiling_group(r)]),
            theirs("retained_revenue_ceiling"),
            amount,
            matches=matches,
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


# -- §13 check 8: law status, the note in the export's last column -----------------------------

LAW_STATUS_COLUMNS = ("law_key", "status", "note")
# Differences that carry a known reason (§13 check 4): they don't stop a law being "checked"
EXPLAINED_STATUSES = ("flagged", "earlier_laws")
EXCLUDES = (
    "Excludes §2B chargebacks, interim budgets, reauthorizations, carried-over money and "
    "transfers; federal money flagged, not counted."
)


def _dollars(n: int) -> str:
    return f"${n:,}"


def _years(keys: set[str]) -> str:
    years = sorted(keys)
    if not years:
        return ""
    return "FY" + years[0] if len(years) == 1 else "FY" + "–FY".join((years[0], years[-1]))


def _plural(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def _is_federal_share(gap: dict, limits: dict) -> bool:
    lim = limits.get((str(gap["law_key"]), str(gap["section"])), {})
    share = lim.get("federal_share") or ""
    return (
        lim.get("federal_split") == "identified"
        and share != ""
        and int(gap["difference"]) == int(share)
    )


def law_status(
    actions: list[dict[str, str]],
    cthru_rows: list[dict[str, str]],
    limits: list[dict[str, str]],
    law_list: list[dict[str, str]],
) -> list[dict[str, str]]:
    """§13 check 8 (decided by Emma, 2026-11-12): one row per in-scope law with funding actions:
    ``checked``, ``partially_checked`` or ``not_checked``, and a note that the export repeats on
    each of the law's rows (§8 column 19).

    The note states only what was checked. Budget and supplemental items are compared with CTHRU
    exactly, to the dollar, with no tolerance (check 4): the note gives how many match, and the
    dollar gap of those that differ. An item several laws touch is counted for each of them; when
    it differs, the gap can't be attributed to one law, so it is counted as shared, without a
    dollar figure. A difference with a known reason (``flagged``, ``earlier_laws``) doesn't count
    against the law. Bond items are checked against their borrowing limits instead (check 7).
    A law is ``checked`` when nothing compared differs without a reason, ``partially_checked``
    when something does, and ``not_checked`` when nothing could be compared.
    """
    in_scope = {r["law_key"] for r in law_list if r["role"] == "in_scope"}
    by_law: dict[str, list[dict[str, str]]] = {}
    for r in actions:
        if r["law_key"] in in_scope:
            by_law.setdefault(r["law_key"], []).append(r)

    matches: list[dict[str, str]] = []
    mismatches: list[dict[str, str | int]] = []
    if cthru_rows:
        _, mismatches = check_cthru(actions, cthru_rows, law_list, matches)
    _, bond_gaps = check_bond_totals(actions, limits, law_list) if limits else (0, [])

    compared: dict[str, dict[str, list]] = {}
    for m in matches:
        for law in str(m["laws"]).split(";"):
            compared.setdefault(law, {"match": [], "differ": []})["match"].append(m)
    for m in mismatches:
        laws = [law for law in str(m["laws"]).split(";") if law]
        for law in laws:
            compared.setdefault(law, {"match": [], "differ": []})["differ"].append(
                dict(m, shared=len(laws) > 1)
            )
    limits_by_law: dict[str, int] = {}
    for lim in limits:
        if lim["law_key"] in in_scope:
            limits_by_law[lim["law_key"]] = limits_by_law.get(lim["law_key"], 0) + 1
    limit_by_key = {(lim["law_key"], lim["section"]): lim for lim in limits}
    gaps_by_law: dict[str, list[dict[str, str | int]]] = {}
    for g in bond_gaps:
        gaps_by_law.setdefault(str(g["law_key"]), []).append(g)

    out = []
    for law in sorted(by_law, key=combine._law_order):
        rows = by_law[law]
        sentences, problem, anything = [], False, False
        operating = [r for r in rows if r["funding_action"] != "CAP"]
        capital = [r for r in rows if r["funding_action"] == "CAP"]
        if operating and capital and all(r["amount"] in ("", None) for r in operating):
            operating = []  # only wording changes beside the bond items: nothing to say
        if operating:
            money = [r for r in operating if r["amount"] not in ("", None)]
            first = (
                f"{_plural(len(money), 'row', 'rows')} with an amount, net new "
                f"{_dollars(combine.operating_total(operating))}"
            )
            seen = compared.get(law, {"match": [], "differ": []})
            n_match, differ = len(seen["match"]), seen["differ"]
            if n_match or differ:
                anything = True
                years = _years({str(m["fiscal_year"]) for m in seen["match"] + differ})
                total = n_match + len(differ)
                explained = [d for d in differ if d["status"] in EXPLAINED_STATUSES]
                own = [d for d in differ if d not in explained and not d["shared"]]
                shared = [d for d in differ if d not in explained and d["shared"]]
                if not differ and total == 1:
                    first += f"; the 1 item compared matches CTHRU {years} (difference $0)"
                elif not differ:
                    first += f"; all {total:,} items compared match CTHRU {years} (difference $0)"
                else:
                    compared_items = _plural(total, "item compared", "items compared")
                    first += f"; {n_match:,} of {compared_items} match CTHRU {years}"
                parts = []
                if own:
                    gap = sum(abs(int(d["difference"])) for d in own)
                    parts.append(
                        f"{_plural(len(own), 'item differs', 'items differ')} by "
                        f"{_dollars(gap)} in total"
                    )
                if shared:
                    parts.append(
                        f"{_plural(len(shared), 'item differs', 'items differ')} but "
                        f"{'is' if len(shared) == 1 else 'are'} shared with other laws, so the "
                        "gap can't be attributed to this law"
                    )
                if explained:
                    parts.append(
                        f"{_plural(len(explained), 'difference has', 'differences have')} a "
                        "known reason"
                    )
                if parts:
                    first += "; " + "; ".join(parts)
                problem = problem or bool(own or shared)
            else:
                first += "; no item could be compared with CTHRU"
            sentences.append(first + ".")
            sentences.append(EXCLUDES)
        if capital:
            text = (
                f"Capital authorizations {_dollars(combine.capital_total(capital))} "
                "(not counted in operating totals)"
            )
            n_limits = limits_by_law.get(law, 0)
            differ = [g for g in gaps_by_law.get(law, []) if g["status"] != "no_limit"]
            # a gap that is exactly the limit's identified federal share is that share (§10, New 1)
            federal = [g for g in differ if _is_federal_share(g, limit_by_key)]
            gaps = [g for g in differ if g not in federal]
            if n_limits:
                anything = True
                n_ok = n_limits - len(differ)
                if n_limits == 1 and not differ:
                    text += "; the 1 borrowing limit matches its items"
                elif not differ:
                    text += f"; all {n_limits:,} borrowing limits match their items"
                else:
                    text += f"; {n_ok:,} of {n_limits:,} borrowing limits match their items"
                if gaps:
                    gap = sum(abs(int(g["difference"])) for g in gaps)
                    text += (
                        f", and {_plural(len(gaps), 'differs', 'differ')} by "
                        f"{_dollars(gap)} in total"
                    )
                    problem = True
                if federal:
                    text += (
                        f"; {_plural(len(federal), 'limit is', 'limits are')} below "
                        f"{'its' if len(federal) == 1 else 'their'} items by exactly the "
                        "identified federal share, which is left out of the capital total"
                    )
            else:
                text += "; no borrowing limit of this law to compare with"
            sentences.append(text + ".")
        if not anything:
            status = "not_checked"
            lead = "Total not checked against CTHRU."
        elif problem:
            status, lead = "partially_checked", "Total partly checked:"
        else:
            status, lead = "checked", "Total checked:"
        out.append({"law_key": law, "status": status, "note": " ".join([lead, *sentences])})
    return out


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
    orphaned = check_orphaned_explanations(ctx)
    write_problems(out / "unread_explanations_orphaned.csv", orphaned, ctx.root)
    for path, p in schema_problems + unread:
        print(f"  {path.name}:{p.row} {p.column}: {p.message}")
    print(
        f"  schema problems: {len(schema_problems)}; unexplained unread rows: {len(unread)}"
    )
    if orphaned:
        print(
            f"  explanations matching no unread row: {len(orphaned)} in "
            "unread_explanations_orphaned.csv (reported, not a failure)"
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
            " (each goes to a person: Q21, Q27)"
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
    if actions:
        law_list = _read_rows(ctx.config_dir / "law_list.csv")
        status = law_status(actions, cthru_rows, limits, law_list)
        _write_report(ctx.reports_dir / "law_status.csv", LAW_STATUS_COLUMNS, status)
        counts = {s: sum(r["status"] == s for r in status) for s in schemas.LAW_STATUSES}
        print(
            f"  law status: {counts['checked']} checked, {counts['partially_checked']} partly "
            f"checked, {counts['not_checked']} not checked, in reports/law_status.csv"
        )
    return 1 if schema_problems or unread else 0
