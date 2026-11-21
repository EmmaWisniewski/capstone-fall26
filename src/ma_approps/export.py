"""Stage 8 `export`: apply review/corrections.csv and write the dataset (DESIGN §7.11–§7.13, §8,
§14).

Owner: everyone (Putting it together), coordinated by E. Writes
data/output/ma_appropriations_cy2021_2025.csv (schemas.EXPORT_COLUMNS, sorted by record_id).
The last column, "Source or calculation for total", is each law's note from
``validate.law_status`` (§13 check 8). It also writes review/review_queue.csv, every row that
needs a person (§7.12, ``review_queue``). Still to build: the extended export and the data
dictionary.

The capital file (workstream A, Q5/Q16) is built here already: ``capital_rows`` and
``write_capital_file``. ``main_columns`` fills the 20 main-export columns from a funding-action row,
so the main file can reuse it and both files say the same thing.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from ma_approps import combine, schemas, validate
from ma_approps.context import Context

IMPLEMENTED = True

# Until the label stage (D) writes labels.csv: the placeholders of §8 (partner, 2026-11-06) and the
# interim rules for bond rows (Emma, 2026-11-10). A labels.csv row replaces them.
PLACEHOLDERS = {
    "program_purpose": "",
    "policy_area": "Not classified",
    "previously_funded": "Unknown",
    "one_time_or_recurring": "One-time",
    "new_or_reapprop": "Pending",
}
TOTAL_NOT_CHECKED = "Total not yet checked."
FEDERAL_SPLIT_LABELS = {"identified": "Identified", "unknown": "Unknown", "none": "None"}


def output_name(stem: str, settings: Mapping[str, Any]) -> str:
    """``{stem}_cy{first}_{last}.csv`` from the scope's approval dates (``…_cy2021_2025.csv``)."""
    scope = settings["scope"]
    return f"{stem}_cy{scope['approved_from'][:4]}_{scope['approved_to'][:4]}.csv"


def _money(value: Any) -> str:
    return f"{int(value):,}" if str(value).strip() not in ("", "None") else ""


def _us_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%m/%d/%Y") if value else ""


def main_columns(
    row: Mapping[str, Any],
    law: Mapping[str, str],
    label: Mapping[str, str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    """The 20 main-export columns (§8, schemas.EXPORT_COLUMNS) for one funding-action row.

    ``label`` is the row's labels.csv row, if the label stage has written one. Corrections
    (§7.11) and the law-level total note (column 19) come later with the main file.
    """
    label = label or {}

    def lab(key: str) -> str:
        return label.get(key) or PLACEHOLDERS[key]

    agency = label.get("agency_office") or str(row["agency_header_raw"]).strip().rstrip(".")
    return {
        "Record ID": row["record_id"],
        "Law citation": f"{law['acts_year']} Acts, ch. {law['chapter']}",
        "Law name": law["law_name"],
        "Enactment date": _us_date(str(row["event_date"])),
        "Calendar year": row["calendar_year"],
        "Fiscal year": row["fiscal_year"],
        "Section": row["section"],
        "Line item": row["line_item"],
        "Agency / office": agency,
        "Program / purpose": lab("program_purpose"),
        "Policy area": lab("policy_area"),
        "Funding action": schemas.FUNDING_ACTION_LABELS[row["funding_action"]],
        "Appropriation/change ($)": _money(row["amount"]),
        "Veto status": row["veto_status"],
        "Previously funded?": lab("previously_funded"),
        "One-time or recurring funding": lab("one_time_or_recurring"),
        "New funding appropriation or re-appropriation of existing funding?": lab(
            "new_or_reapprop"
        ),
        "Human review status": "Not human reviewed",
        "Source URL": row["source_url"],
        "Source or calculation for total": note or TOTAL_NOT_CHECKED,
    }


def limit_note(limit: Mapping[str, str]) -> str:
    """The Limit difference note (Q11): which limit covers the item and how far its items are from
    it, e.g. "covered by §4: items exceed the borrowing limit by $400,000,000"."""
    gap = int(limit["items_total"] or 0) - int(limit["authorized"] or 0)
    if not gap:
        return ""
    where = f"covered by §{limit['section']}"
    if gap < 0:
        return f"{where}: items are ${-gap:,} less than the borrowing limit"
    note = f"{where}: items exceed the borrowing limit by ${gap:,}"
    if limit["federal_split"] == "identified":
        note += " (the identified federal share)"
    return note


def capital_rows(
    funding_actions: list[Mapping[str, Any]],
    limits: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    labels: list[Mapping[str, str]] = (),
    notes: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """The capital file (§7.13): every ``CAP`` row, sorted by Record ID, with the 20 main columns
    and the details of the borrowing limit that covers it (Q16).

    A later law's change to a bond item (issue #41, e.g. 2021-25 §3 raising 2020-383 item
    6121-2118) takes the limit that covers the item it changes: the amending section itself is
    outside any capital section (2021-25 §11 covers only its own §2)."""
    laws = {r["law_key"]: r for r in law_list}
    by_id = {r["record_id"]: r for r in labels}
    # (law, item) -> the capital section that prints it, from the bond laws' own rows
    item_section = {
        (r["law_key"], r["line_item"]): r["section"]
        for r in funding_actions
        if r["funding_action"] == "CAP" and r["law_key"] == r["target_law_key"]
    }
    out = []
    for row in sorted(funding_actions, key=lambda r: r["record_id"]):
        if row["funding_action"] != "CAP":
            continue
        covered = row
        if row["target_law_key"] and row["target_law_key"] != row["law_key"]:
            key = (row["target_law_key"], row["line_item"])
            covered = {"law_key": key[0], "section": item_section.get(key, ""), "line_item": key[1]}
        limit = combine.limit_for(covered, limits) or {}
        split = limit.get("federal_split", "")
        out.append(
            {
                **main_columns(
                    row,
                    laws[row["law_key"]],
                    by_id.get(row["record_id"]),
                    (notes or {}).get(row["law_key"], ""),
                ),
                "Borrowing limit section": limit.get("section", ""),
                "Borrowing limit ($)": _money(limit.get("authorized", "")),
                "Total of items under this limit ($)": _money(limit.get("items_total", "")),
                "Identified federal share ($)": (
                    _money(limit["federal_share"]) if split == "identified" else ""
                ),
                "Federal split": FEDERAL_SPLIT_LABELS.get(split, ""),
                "Limit difference note": limit_note(limit) if limit else "",
                "Bond name": limit.get("bond_name", ""),
                "Maximum term (years)": limit.get("max_term_years", ""),
                "Final payable date": _us_date(limit.get("payable_by", "")),
                "Fund paying the bonds": limit.get("paying_fund", ""),
                "Spending authority through": _us_date(
                    str(row.get("available_through") or limit.get("available_through", ""))
                ),
            }
        )
    return out


def law_notes(ctx: Context) -> dict[str, str]:
    """Each in-scope law's total note (§8 column 19), from ``validate.law_status`` on this run's
    files. ``export`` runs before ``validate``, so it works the notes out itself rather than reading
    a ``reports/law_status.csv`` from an earlier run; both use the same code, so they agree."""
    status = validate.law_status(
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.interim_dir / "cthru_line_items.csv"),
        _read(ctx.interim_dir / "bond_authorizations_raw.csv"),
        _read(ctx.config_dir / "law_list.csv"),
    )
    return {r["law_key"]: r["note"] for r in status}


def _read(path: Path) -> list[dict[str, str]]:
    return schemas.read_csv(path)[1] if path.exists() else []


def write_capital_file(ctx: Context, notes: Mapping[str, str] | None = None) -> Path:
    """Write the capital file from combine's and read_bonds' output; returns its path."""
    rows = capital_rows(
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.interim_dir / "bond_authorizations_raw.csv"),
        _read(ctx.config_dir / "law_list.csv"),
        _read(ctx.interim_dir / "labels.csv"),
        law_notes(ctx) if notes is None else notes,
    )
    path = ctx.output_dir / output_name("ma_capital_authorizations", ctx.settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.CAPITAL_EXPORT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    no_limit = sum(1 for r in rows if not r["Borrowing limit section"])
    print(f"  capital file: {len(rows)} rows ({no_limit} without a borrowing limit): {path.name}")
    return path


AUTOMATIC = "department list (automatic)"


def _catalog_deciders(catalog: list[Mapping[str, str]]) -> dict[str, str]:
    return {r["line_item"]: (r.get("decided_by") or "").strip() for r in catalog}


def human_policy_area(
    row: Mapping[str, Any], label: Mapping[str, str], deciders: Mapping[str, str]
) -> bool:
    """§8 column 17: did a person decide this row's policy area? A catalog row decided by a named
    person does; one marked ``department list (automatic)`` does not, and neither does the
    department table (a person chose each department's area, nobody checked the line)."""
    method = label.get("policy_area_method", "")
    if method == "human":
        return True
    if method == "catalog":
        who = deciders.get(str(row["line_item"]), "")
        return bool(who) and who != AUTOMATIC
    return False


def main_rows(
    funding_actions: list[Mapping[str, Any]],
    law_list: list[Mapping[str, str]],
    labels: list[Mapping[str, str]],
    catalog: list[Mapping[str, str]],
    corrections: list[Mapping[str, str]],
    settings: Mapping[str, Any],
    notes: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """The main file (§7.13): the funding-action rows inside the approval-date window, bonds left
    out (they go to the capital file), sorted by Record ID, with corrections (§7.11) applied.
    Wording-only changes to bond items (``PURP`` rows with ``section_type = capital``) are left
    out of both files and belong in the extended file only (Decision Log, 2026-11-11).

    Returns (rows, warnings). A correction is skipped, with a warning, when its field isn't an
    export column or its ``expected_old_value`` no longer matches the cell."""
    scope = settings["scope"]
    first, last = (
        date.fromisoformat(scope["approved_from"]),
        date.fromisoformat(scope["approved_to"]),
    )
    laws = {r["law_key"]: r for r in law_list}
    by_id = {r["record_id"]: r for r in labels}
    deciders = _catalog_deciders(catalog)
    fixes: dict[str, list[Mapping[str, str]]] = {}
    for c in corrections:
        fixes.setdefault(c["record_id"], []).append(c)

    warnings, out = [], []
    for row in sorted(funding_actions, key=lambda r: r["record_id"]):
        if row["funding_action"] == "CAP":
            continue
        if row.get("section_type") == "capital":
            # a wording-only change to a bond item: the extended file only (2026-11-11)
            continue
        if not first <= date.fromisoformat(str(row["event_date"])) <= last:
            continue
        label = by_id.get(row["record_id"], {})
        cells = main_columns(
            row, laws[row["law_key"]], label, (notes or {}).get(row["law_key"], "")
        )
        human = human_policy_area(row, label, deciders)
        for c in fixes.get(row["record_id"], []):
            field = c["field"]
            if field not in schemas.EXPORT_COLUMNS:
                warnings.append(f"{row['record_id']}: correction of unknown column {field!r}")
            elif c.get("expected_old_value") and c["expected_old_value"] != str(cells[field]):
                warnings.append(
                    f"{row['record_id']}: {field!r} is {cells[field]!r}, not the expected "
                    f"{c['expected_old_value']!r}; correction skipped"
                )
            else:
                cells[field] = c["new_value"]
                human = True
        cells["Human review status"] = "Human reviewed" if human else "Not human reviewed"
        out.append(cells)
    return out, warnings


def write_main_file(ctx: Context, notes: Mapping[str, str] | None = None) -> Path:
    """Write the main file from combine's and label's output; returns its path."""
    rows, warnings = main_rows(
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.config_dir / "law_list.csv"),
        _read(ctx.interim_dir / "labels.csv"),
        _read(ctx.config_dir / "line_item_catalog.csv"),
        _read(ctx.review_dir / "corrections.csv"),
        ctx.settings,
        law_notes(ctx) if notes is None else notes,
    )
    path = ctx.output_dir / output_name("ma_appropriations", ctx.settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.EXPORT_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for w_ in warnings:
        print(f"  WARNING: {w_}")
    reviewed = sum(r["Human review status"] == "Human reviewed" for r in rows)
    print(f"  main file: {len(rows)} rows ({reviewed} human reviewed): {path.name}")
    return path


# -- review/review_queue.csv (§7.12, §14) --------------------------------------------------------

QUEUE_COLUMNS = (
    *(c.name for c in schemas.REVIEW_QUEUE_LEADING),
    "law_key",
    "fiscal_year",
    "line_item",
    "detail",
    "where_to_record",
)
# reason -> (priority, where a person records the decision). 1 changes a total, chart or flag.
REASONS = {
    "policy_area": (
        1,
        "config/line_item_catalog.csv (review/corrections.csv for a 1599 reserve)",
    ),
    "cthru_mismatch": (1, "a fix, or the explanation in review/research_log.md"),
    "unknown_fund": (1, "config/funds.csv"),
    "amendment_check": (2, "review/corrections.csv, or review/research_log.md"),
    "borrowing_limit": (2, "review/research_log.md"),
    "combine_problem": (3, "depends on the problem; review/research_log.md"),
}
UNKNOWN_FUND = "fund not in config/funds.csv"


def review_queue(
    exported: list[Mapping[str, Any]],
    actions: list[Mapping[str, str]],
    cthru_rows: list[dict[str, str]],
    law_list: list[dict[str, str]],
    limits: list[dict[str, str]],
    amendments: list[Mapping[str, Any]],
    problems: list[Mapping[str, str]],
) -> list[dict[str, Any]]:
    """Every row of the main and capital files (``exported``, corrections applied) that needs a
    person, one line per row and reason, most urgent first (§7.12). Built from the checks the
    program already runs, so it is never out of date:

    - ``policy_area``: the row still has no policy area.
    - ``cthru_mismatch``: our amount for that fiscal year and item differs from CTHRU's and isn't
      flagged or explained (``validate.check_cthru``).
    - ``unknown_fund``: the law names a fund missing from config/funds.csv, so the program can't
      tell whether it is federal (``combine_problems.csv``); ``combine_problem`` for the rest.
    - ``amendment_check``: an amendment whose struck figure didn't check out (Q21, Q27).
    - ``borrowing_limit``: a bond item under a borrowing limit its items don't add up to (Q11).

    A problem with no row in the files (money CTHRU has and we don't, a limit with no items)
    gets a blank ``record_id``; ``law_key`` and ``line_item`` say where to look."""
    in_files = {str(r["Record ID"]): r for r in exported}
    by_id = {r["record_id"]: r for r in actions if r["record_id"] in in_files}
    out: list[dict[str, Any]] = []

    def add(reason: str, detail: str, row=None, law_key="", fiscal_year="", line_item="") -> None:
        if row is not None:
            law_key, fiscal_year, line_item = row["law_key"], row["fiscal_year"], row["line_item"]
        priority, where = REASONS[reason]
        out.append(
            {
                "record_id": row["record_id"] if row is not None else "",
                "reason": reason,
                "priority": priority,
                "law_key": law_key,
                "fiscal_year": fiscal_year,
                "line_item": line_item,
                "detail": detail,
                "where_to_record": where,
            }
        )

    for rid, r in in_files.items():
        if r["Policy area"] in ("", PLACEHOLDERS["policy_area"]) and rid in by_id:
            add("policy_area", "no policy area yet", by_id[rid])

    _, mismatches = validate.check_cthru(list(actions), cthru_rows, law_list)
    for m in mismatches:
        if m["status"] in validate.EXPLAINED_STATUSES:
            continue
        fy, item = str(m["fiscal_year"]), str(m["line_item"])
        detail = (
            f"{m['check']}: ours ${int(m['our_amount']):,}, CTHRU ${int(m['cthru_amount']):,} "
            f"({str(m['status']).replace('_', ' ')})"
        )
        rows = [
            r
            for r in by_id.values()
            if r["fiscal_year"] == fy and r["line_item"] == item and r["law_key"] in m["laws"]
        ]
        for r in rows:
            add("cthru_mismatch", detail, r)
        if not rows:
            add("cthru_mismatch", detail, fiscal_year=fy, line_item=item)

    for p in problems:
        reason = "unknown_fund" if p["problem"].startswith(UNKNOWN_FUND) else "combine_problem"
        row = by_id.get(p["record_id"])
        if row is not None:
            add(reason, p["problem"], row)
        elif not p["record_id"]:
            add(reason, p["problem"], law_key=p["law_key"], line_item=p["line_item"])

    in_scope = {r["law_key"] for r in law_list if r["role"] == "in_scope"}
    for a in amendments:
        # amendments in reference-only laws (read only to follow an item's amount) aren't data
        if a["review"] != "true" or a["law_key"] not in in_scope:
            continue
        detail = f"§{a['section']} changes {a['target_item']}: {a['check']}"
        if a.get("note"):
            detail += f"; {a['note']}"
        rows = [
            r
            for r in by_id.values()
            if r["law_key"] == a["law_key"]
            and r["section"] == a["section"]
            and r["line_item"] == a["target_item"]
        ]
        for r in rows:
            add("amendment_check", detail, r)
        if not rows:
            add("amendment_check", detail, law_key=a["law_key"], line_item=a["target_item"])

    _, gaps = validate.check_bond_totals(list(actions), limits, law_list)
    for g in gaps:
        items = str(g["line_items"]).split(";") if g["line_items"] else []
        rows = [
            r
            for r in by_id.values()
            if r["funding_action"] == "CAP"
            and r["law_key"] == g["law_key"]
            and r["line_item"] in items
            and (g["status"] != "no_limit" or r["section"] == g["section"])
        ]
        for r in rows:
            add("borrowing_limit", str(g["note"]), r)
        if not rows:
            add("borrowing_limit", str(g["note"]), law_key=str(g["law_key"]))

    seen, unique = set(), []
    for q in out:
        key = (q["record_id"], q["reason"], q["detail"], q["law_key"], q["line_item"])
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return sorted(
        unique,
        key=lambda q: (
            q["priority"],
            q["reason"],
            q["fiscal_year"],
            q["line_item"],
            q["law_key"],
            q["record_id"],
        ),
    )


def write_review_queue(ctx: Context, main_path: Path, capital_path: Path) -> Path:
    """Write review/review_queue.csv from this run's files; returns its path."""
    rows = review_queue(
        _read(main_path) + _read(capital_path),
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.interim_dir / "cthru_line_items.csv"),
        _read(ctx.config_dir / "law_list.csv"),
        _read(ctx.interim_dir / "bond_authorizations_raw.csv"),
        validate.check_amendment_amounts(ctx) or [],
        _read(ctx.reports_dir / "combine_problems.csv"),
    )
    path = ctx.review_dir / "review_queue.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    counts = Counter(q["reason"] for q in rows)
    summary = ", ".join(f"{counts[r]} {r}" for r in REASONS if counts[r]) or "nothing"
    print(f"  review queue: {len(rows)} rows ({summary}): {path.name}")
    return path


def run(ctx: Context) -> int:
    notes = law_notes(ctx)
    main_path = write_main_file(ctx, notes)
    capital_path = write_capital_file(ctx, notes)
    write_review_queue(ctx, main_path, capital_path)
    return 0
