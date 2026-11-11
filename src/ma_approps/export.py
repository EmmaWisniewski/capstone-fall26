"""Stage 8 `export`: apply review/corrections.csv and write the dataset (DESIGN §7.11–§7.13, §8,
§14).

Stub for the main file. Owner: everyone (Putting it together), coordinated by E. Writes
data/output/ma_appropriations_cy2021_2025.csv (schemas.EXPORT_COLUMNS, sorted by record_id), the
extended export, and review/review_queue.csv.

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

IMPLEMENTED = False  # until the main file exists (the example-rows test runs once it's True)

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
    and the details of the borrowing limit that covers it (Q16)."""
    laws = {r["law_key"]: r for r in law_list}
    by_id = {r["record_id"]: r for r in labels}
    out = []
    for row in sorted(funding_actions, key=lambda r: r["record_id"]):
        if row["funding_action"] != "CAP":
            continue
        limit = combine.limit_for(row, limits) or {}
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


def run(ctx: Context) -> int:
    write_capital_file(ctx)
    print("  main file (E): not built yet")
    return 0
