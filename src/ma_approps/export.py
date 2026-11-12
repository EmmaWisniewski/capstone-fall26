"""Stage 8 `export`: apply review/corrections.csv and write the dataset (DESIGN §7.11–§7.13, §8,
§14).

Owner: everyone (Putting it together), coordinated by E. Writes
data/output/ma_appropriations_cy2021_2025.csv (schemas.EXPORT_COLUMNS, sorted by record_id).
Still to build: the extended export, the data dictionary and review/review_queue.csv, and the
law-level total note (column 19, from validate's law status) in place of "Total not yet checked."

The capital file (workstream A, Q5/Q16) is built here already: ``capital_rows`` and
``write_capital_file``. ``main_columns`` fills the 20 main-export columns from a funding-action row,
so the main file can reuse it and both files say the same thing.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from ma_approps import combine, schemas
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
    row: Mapping[str, Any], law: Mapping[str, str], label: Mapping[str, str] | None = None
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
        "Source or calculation for total": TOTAL_NOT_CHECKED,
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
                **main_columns(row, laws[row["law_key"]], by_id.get(row["record_id"])),
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


def _read(path: Path) -> list[dict[str, str]]:
    return schemas.read_csv(path)[1] if path.exists() else []


def write_capital_file(ctx: Context) -> Path:
    """Write the capital file from combine's and read_bonds' output; returns its path."""
    rows = capital_rows(
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.interim_dir / "bond_authorizations_raw.csv"),
        _read(ctx.config_dir / "law_list.csv"),
        _read(ctx.interim_dir / "labels.csv"),
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
) -> tuple[list[dict[str, Any]], list[str]]:
    """The main file (§7.13): the funding-action rows inside the approval-date window, bonds left
    out (they go to the capital file), sorted by Record ID, with corrections (§7.11) applied.

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
        if not first <= date.fromisoformat(str(row["event_date"])) <= last:
            continue
        label = by_id.get(row["record_id"], {})
        cells = main_columns(row, laws[row["law_key"]], label)
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


def write_main_file(ctx: Context) -> Path:
    """Write the main file from combine's and label's output; returns its path."""
    rows, warnings = main_rows(
        _read(ctx.interim_dir / "funding_actions.csv"),
        _read(ctx.config_dir / "law_list.csv"),
        _read(ctx.interim_dir / "labels.csv"),
        _read(ctx.config_dir / "line_item_catalog.csv"),
        _read(ctx.review_dir / "corrections.csv"),
        ctx.settings,
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


def run(ctx: Context) -> int:
    write_main_file(ctx)
    write_capital_file(ctx)
    return 0
