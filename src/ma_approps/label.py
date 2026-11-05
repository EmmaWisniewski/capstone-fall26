"""Stage 7 `label`: agency, purpose, policy area and yes/no columns to labels.csv
(DESIGN §7.9, §8, §12).

Owner: workstream D (Labels). No LLM.

Done so far:
- Policy area (§12): config/line_item_catalog.csv, then config/department_policy_areas.csv
  (via the line's CTHRU department that fiscal year), else empty, which sends the row to the
  review queue.
- Previously funded? (§8 column 14, Q3): ``Yes`` if the line had non-zero enacted authority in
  the fiscal year before the row's, else ``No``.
- One-time or recurring (§8 column 15, Q3): a GAA row is ``Recurring`` if the line was also in
  the GAA the year before or the year after, else ``One-time``. Supplemental and bond rows are
  ``One-time`` (interim rule).

Still to do: Agency / office and Program / purpose (§8 columns 9-10). New vs. re-appropriation
stays ``Pending`` until the partner answers Q3.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = False  # set True once agency and purpose are done

# Funding actions that add or remove enacted authority (§9.2). Reauthorizations, transfers,
# purpose changes and interim budgets don't fund a line on their own.
AUTHORITY_ACTIONS = frozenset(("ORIG", "NEW", "INC", "RED", "VETO", "OVR", "CAP"))
ONE_TIME_ACTIONS = frozenset(("NEW", "INC", "RED", "CAP"))

Row = Mapping[str, str]


def _int(value: str | None) -> int:
    return int(value) if value else 0


# ---------------------------------------------------------------------------
# Policy area (§12)
# ---------------------------------------------------------------------------


def policy_area(
    line_item: str,
    fiscal_year: int,
    catalog: Mapping[str, Row],
    departments: Mapping[str, Row],
    cthru: Mapping[tuple[str, int], Row],
) -> tuple[str, str]:
    """Return ``(policy_area, policy_area_method)``. ``("", "")`` means the row needs review."""
    entry = catalog.get(line_item)
    if entry is not None:
        if entry["label_every_year"] == "true":
            return "", ""
        return entry["policy_area"], "catalog"
    account = cthru.get((line_item, fiscal_year))
    dept = departments.get(account["department_code"]) if account else None
    if dept and dept["mixed"] == "false" and dept["policy_area"]:
        return dept["policy_area"], "department"
    return "", ""


# ---------------------------------------------------------------------------
# Previously funded? and One-time or recurring (§8 columns 14-15)
# ---------------------------------------------------------------------------


def funded_years(
    cthru_rows: Iterable[Row], funding_rows: Iterable[Row]
) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
    """Return ``(funded, gaa_funded)``: sets of ``(line_item, fiscal_year)``.

    ``funded`` has any non-zero enacted authority that year, from CTHRU or the funding actions
    table. ``gaa_funded`` has non-zero authority in that year's GAA (original appropriation or
    retained-revenue ceiling).
    """
    funded: set[tuple[str, int]] = set()
    gaa: set[tuple[str, int]] = set()
    for r in cthru_rows:
        k = (r["line_item"], int(r["fiscal_year"]))
        if _int(r["original_enacted"]) or _int(r["retained_revenue_ceiling"]):
            gaa.add(k)
            funded.add(k)
        if _int(r["supplemental"]) or _int(r["total_enacted"]):
            funded.add(k)
    net: dict[tuple[str, int], int] = defaultdict(int)
    for r in funding_rows:
        if not r["line_item"] or r["funding_action"] not in AUTHORITY_ACTIONS:
            continue
        k = (r["line_item"], int(r["fiscal_year"]))
        net[k] += _int(r["amount"])
        if r["funding_action"] == "ORIG" and _int(r["amount"]):
            gaa.add(k)
    funded.update(k for k, amount in net.items() if amount)
    return funded, gaa


def previously_funded(line_item: str, fiscal_year: int, funded: set[tuple[str, int]]) -> str:
    """Q3: the year before only. A row with no line item can't be checked."""
    if not line_item:
        return "Unknown"
    return "Yes" if (line_item, fiscal_year - 1) in funded else "No"


def one_time_or_recurring(row: Row, gaa_funded: set[tuple[str, int]]) -> str:
    """Q3: recurring means in at least 2 consecutive GAAs, so first years count."""
    line_item, action = row["line_item"], row["funding_action"]
    if not line_item:
        return "Not classified"
    if action == "ORIG":
        fy = int(row["fiscal_year"])
        if (line_item, fy - 1) in gaa_funded or (line_item, fy + 1) in gaa_funded:
            return "Recurring"
        return "One-time"
    if action in ONE_TIME_ACTIONS:
        return "One-time"
    return "Not classified"


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def label_rows(
    funding_rows: list[Row],
    cthru_rows: list[Row],
    catalog_rows: Iterable[Row],
    department_rows: Iterable[Row],
) -> list[dict[str, str]]:
    """One labels.csv row per funding-action row, sorted by record_id."""
    catalog = {r["line_item"]: r for r in catalog_rows}
    departments = {r["department_code"]: r for r in department_rows}
    cthru = {(r["line_item"], int(r["fiscal_year"])): r for r in cthru_rows}
    funded, gaa_funded = funded_years(cthru_rows, funding_rows)
    out = []
    for r in funding_rows:
        fy = int(r["fiscal_year"])
        area, method = policy_area(r["line_item"], fy, catalog, departments, cthru)
        label = dict.fromkeys(schemas.columns("labels"), "")
        label.update(
            record_id=r["record_id"],
            policy_area=area,
            policy_area_method=method,
            previously_funded=previously_funded(r["line_item"], fy, funded),
            one_time_or_recurring=one_time_or_recurring(r, gaa_funded),
            new_or_reapprop="Pending",
        )
        out.append(label)
    return sorted(out, key=lambda r: r["record_id"])


def write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.columns("labels"), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(ctx: Context) -> int:
    inputs = {
        "funding_actions": ctx.interim_dir / "funding_actions.csv",
        "cthru_line_items": ctx.interim_dir / "cthru_line_items.csv",
        "line_item_catalog": ctx.config_dir / "line_item_catalog.csv",
        "department_policy_areas": ctx.config_dir / "department_policy_areas.csv",
    }
    missing = [str(p) for p in inputs.values() if not p.exists()]
    if missing:
        print(f"  missing input: {', '.join(missing)}")
        return 1
    rows = {name: schemas.read_csv(path)[1] for name, path in inputs.items()}
    labels = label_rows(
        rows["funding_actions"],
        rows["cthru_line_items"],
        rows["line_item_catalog"],
        rows["department_policy_areas"],
    )
    write_labels(ctx.interim_dir / "labels.csv", labels)
    waiting = sum(1 for r in labels if not r["policy_area"])
    print(f"  labels: {len(labels)} rows; {waiting} waiting for a policy-area review")
    return 0
