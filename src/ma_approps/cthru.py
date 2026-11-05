"""Stage 2 `cthru`: Comptroller CTHRU budget data to data/interim/cthru_line_items.csv (DESIGN §3.4,
§7.5).

Owner: workstream E (Annual budgets and checks). For each fiscal year in
``[scope] cthru_fiscal_years`` it downloads every row of Socrata dataset kv7m-35wn into a dated
snapshot, ``data/raw/cthru/{YYYY-MM-DD}/fy{YYYY}.json``, then aggregates the newest snapshot into
one row per fiscal year x account. A snapshot already saved today is reused, not re-downloaded.
``--offline`` skips the download and reads the newest snapshot under the raw directory.

CTHRU has many rows per account per year, one per department and fund, mostly zeros (§3.4). The
amounts are summed over all of them; the department is the one holding the most enacted money.
All CTHRU-specific code lives in this file, so a format change is a one-file fix.

Rules for anyone using cthru_line_items.csv:
1. Fee-revenue items come from the law text. For some items that let an agency spend fees it
   collects ("may expend not more than $X"), CTHRU records the amount only as an estimate, so
   they have no row here. combine takes the printed amount from items_raw instead: about $285M a
   year, e.g. 4000-0320 MassHealth recoveries, $225M.
2. Chargebacks never count toward totals. Fund 0015 rows are §2B ISF chargebacks, one agency
   paying another (e.g. for IT or workers' comp). They show $0 enacted but non-zero fee-revenue
   caps, $632M-$704M a year; counting them would count the same money twice.
3. Federal money is flagged, not counted. Rows in federal funds (is_federal in config/funds.csv,
   e.g. fund 2005, the Federal COVID-19 Response Fund) are kept but left out of the main totals
   (Q1). In FY2022 that is $4.5B of the $56.7B total enacted.

Limitations:
- Authorized amounts only, not actual spending (Q10).
- Budgeted funds only: no bond-funded capital projects (read_bonds reads those from the law text)
  and no §2D federal grants.
- Totals per fiscal year, not per law: ``supplemental`` adds up every supplemental budget for that
  year. Which law made each change comes from the law text.
- No fund splits: each funded account sits in one fund in CTHRU, so splits come from the law text.
- Some account names are cut short (1231-1000: "FOR THE RATE RELIEF COMPONENT OF THE").
- CTHRU updates daily and can revise past years. The dated snapshot records what was used.
- FY2025 lists only 12 chargeback accounts ($215M), against about 36 in earlier years. Not yet
  explained; it doesn't change totals (rule 2).
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = True

PAGE_SIZE = 50000

# §7.5 money columns -> CTHRU fields they sum
AMOUNT_FIELDS = {
    "original_enacted": "original_enacted_budget",
    "supplemental": "supplemental_budget_appropriations",
    "retained_revenue_ceiling": "authorized_retained_revenue_ceiling",
    "total_enacted": "total_enacted_budget_appropriation",
}


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _user_agent(http: dict[str, Any]) -> str:
    email = http.get("contact_email")
    return f"{http['user_agent']} {email}".strip() if email else http["user_agent"]


def _get_json(session: requests.Session, url: str, params: dict, http: dict) -> list[dict]:
    """GET with exponential backoff on 429/5xx and connection errors (§15 politeness)."""
    for attempt in range(http["max_retries"] + 1):
        try:
            r = session.get(url, params=params, timeout=http["timeout_seconds"])
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
                return r.json()
            error: Exception = requests.HTTPError(f"HTTP {r.status_code}", response=r)
        except requests.ConnectionError as e:
            error = e
        if attempt == http["max_retries"]:
            raise error
        time.sleep(http["backoff_base_seconds"] * 2**attempt)
    raise AssertionError("unreachable")


def download_fy(ctx: Context, session: requests.Session, fy: int) -> dict[str, Any]:
    """Every kv7m-35wn row for one fiscal year, paged in a stable order."""
    http = ctx.settings["http"]
    url = ctx.settings["sources"]["cthru_dataset"]
    rows: list[dict] = []
    while True:
        params = {
            "$where": f"fiscal_year = {fy}",
            "$order": ":id",
            "$limit": PAGE_SIZE,
            "$offset": len(rows),
        }
        page = _get_json(session, url, params, http)
        rows += page
        if len(page) < PAGE_SIZE:
            break
        time.sleep(http["min_interval_seconds"])
    return {
        "dataset": url,
        "fiscal_year": fy,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "row_count": len(rows),
        "rows": rows,
    }


def snapshot(ctx: Context, today: date | None = None) -> Path:
    """Save today's snapshot of every configured fiscal year; reuse files already saved today."""
    folder = ctx.raw_dir / "cthru" / (today or date.today()).isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = _user_agent(ctx.settings["http"])
    for fy in ctx.settings["scope"]["cthru_fiscal_years"]:
        path = folder / f"fy{fy}.json"
        if path.exists():
            print(f"  FY{fy}: already downloaded today, reusing {path.name}")
            continue
        data = download_fy(ctx, session, fy)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
        print(f"  FY{fy}: downloaded {data['row_count']:,} rows")
        time.sleep(ctx.settings["http"]["min_interval_seconds"])
    return folder


def latest_snapshot(ctx: Context) -> Path:
    base = ctx.raw_dir / "cthru"
    folders = sorted(p for p in base.glob("????-??-??") if p.is_dir()) if base.exists() else []
    if not folders:
        raise FileNotFoundError(f"no CTHRU snapshot under {base}; run without --offline first")
    return folders[-1]


def load_snapshot(folder: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(folder.glob("fy*.json")):
        rows += json.loads(path.read_text("utf-8"))["rows"]
    return rows


# ---------------------------------------------------------------------------
# Aggregate (§7.5)
# ---------------------------------------------------------------------------


def _dollars(value: str | None) -> int:
    """CTHRU sends numbers as strings like ``"9310231.0"``; round to whole dollars."""
    return round(float(value)) if value not in (None, "") else 0


def line_item(account_number: str) -> str:
    """``23300100`` -> ``2330-0100``."""
    digits = account_number.strip()
    if not (len(digits) == 8 and digits.isdigit()):
        raise ValueError(f"not an 8-digit account number: {account_number!r}")
    return f"{digits[:4]}-{digits[4:]}"


def _department_rank(rows: list[dict]) -> tuple:
    """Sort key: the department holding the most enacted money wins; ties go to more money of any
    authorized kind, then the department code, so the choice is deterministic."""
    total = sum(abs(_dollars(r.get("total_enacted_budget_appropriation"))) for r in rows)
    orig = sum(abs(_dollars(r.get("original_enacted_budget"))) for r in rows)
    ceiling = sum(abs(_dollars(r.get("authorized_retained_revenue_ceiling"))) for r in rows)
    available = sum(abs(_dollars(r.get("total_available_for_spending"))) for r in rows)
    return (-total, -orig, -ceiling, -available, rows[0].get("department_code") or "")


def _has_money(row: dict) -> bool:
    return any(_dollars(row.get(f)) for f in AMOUNT_FIELDS.values())


def aggregate(rows: list[dict]) -> list[dict[str, str]]:
    """One §7.5 row per fiscal year x account, sorted by fiscal year then line item.

    Accounts with no enacted money that year are left out: CTHRU lists closed accounts every year,
    and accounts living only on carried-forward balances or transfers are not appropriations (§7.5).
    """
    by_account: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_account[(_dollars(r["fiscal_year"]), r["appropriation_account_number"])].append(r)

    out = []
    for (fy, account), group in sorted(by_account.items()):
        funded = [r for r in group if _has_money(r)]
        if not funded:  # includes fee items CTHRU only estimates (rule 1 above)
            continue
        by_dept: dict[str, list[dict]] = defaultdict(list)
        for r in group:
            by_dept[r.get("department_code") or ""].append(r)
        dept = min(by_dept.values(), key=_department_rank)[0]
        row = {
            "fiscal_year": str(fy),
            "line_item": line_item(account),
            "account_name": dept.get("appropriation_account_name") or "",
            "department_code": dept.get("department_code") or "",
            "department_name": dept.get("department_name") or "",
            "secretariat": dept.get("cabinet_secretariat_name") or "",
            # 0015 = chargebacks, federal funds per config/funds.csv (rules 2 and 3 above)
            "fund_numbers": ";".join(sorted({r.get("fund_number") or "" for r in funded} - {""})),
        }
        for col, field in AMOUNT_FIELDS.items():
            row[col] = str(sum(_dollars(r.get(field)) for r in group))
        out.append(row)
    return out


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = schemas.columns("cthru_line_items")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(ctx: Context) -> int:
    folder = latest_snapshot(ctx) if ctx.offline else snapshot(ctx)
    print(f"  reading snapshot {folder.name}")
    raw = load_snapshot(folder)
    rows = aggregate(raw)
    accounts = {(r["fiscal_year"], r["appropriation_account_number"]) for r in raw}
    print(f"  skipped {len(accounts) - len(rows):,} account-years with no enacted money")
    out = ctx.interim_dir / "cthru_line_items.csv"
    write_csv(out, rows)

    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        t = totals[r["fiscal_year"]]
        t[0] += 1
        t[1] += int(r["original_enacted"])
        t[2] += int(r["total_enacted"])
    for fy, (n, orig, total) in sorted(totals.items()):
        print(f"  FY{fy}: {n:,} line items; original ${orig:,}; total enacted ${total:,}")
    print(f"  wrote {out}")
    return 0
