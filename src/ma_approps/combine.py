"""Stage 6 `combine`: build funding_actions.csv, fund_splits.csv, running_amounts.csv (DESIGN §5,
§7.6–§7.8).

Stub. Owner: everyone (Putting it together), coordinated by E. GAA rows come from
cthru_line_items.csv; everything else from items_raw, bond_items_raw, amendments_raw and the
manual_rows escape hatch. C owns the running-amounts logic; E owns the CTHRU comparison that sets
veto_status. Use schemas.record_id_prefix / assign_record_ids.

Where GAA amounts come from when CTHRU has none (Mario, 2026-11-04):
- Fee-revenue items ("may expend not more than $X", so items_raw.retained_revenue_ceiling is set)
  use the law's printed amount: amount_source = law_text, flag retained_revenue. CTHRU files these
  under retained_revenue_estimate, which cthru_line_items.csv doesn't keep (e.g. 4000-0320,
  $225M a year; about $285M a year in all).
- §2D federal grant items (section_type = federal_grants) are not in CTHRU at all (about 570 items,
  $5.3B in the FY2024 GAA; 540, $5.5B in FY2025), so a missing CTHRU row says nothing about them.
  Use the law's printed amount: amount_source = law_text, flag federal (Q1), counts_toward_total =
  false until Q1 is decided. CTHRU can't confirm vetoes here: veto_status = unknown, flag
  veto_unverified (a veto marked inline in the law text is still only a hint, §11.4).
- Any other GAA item in a section CTHRU covers (approp_main, surtax) with no CTHRU amount was
  vetoed to $0 (veto_status = vetoed); don't fall back to the printed amount. FY2025's law text
  doesn't mark its vetoes. Apply this only after the two cases above, never to §2D.
- CTHRU fund 0015 is §2B ISF chargebacks: counts_toward_total = false, even though CTHRU gives
  them non-zero fee-revenue caps ($632–704M a year).
"""

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = False

# -- Running amounts and the struck-figure check (workstream C; DESIGN §5.5, §13 check 3) --------

AMOUNT_ACTIONS = ("figure_change", "item_insert", "item_replace", "item_strike")
AMOUNT_COLUMNS = (
    "law_key",
    "section",
    "action_type",
    "target_law_key",
    "target_section",
    "target_item",
    "old_figure",
    "new_figure",
    "amount_before",
    "amount_after",
    "change",
    "check",
    "review",
    "note",
)
# What the struck-figure check found. Figure changes always get one; the other actions only
# `target_not_read`, when the change can't be worked out.
CHECKS = {
    "match": "the struck figure is the item's running amount",
    "already_new": "the item already shows the new figure, so its amount doesn't change",
    "in_item_text": "the struck figure is another figure in the item's text (a cap or an earmark, "
    "Q21), so the item's amount doesn't change",
    "mismatch": "the struck figure is neither the item's running amount nor in its text: "
    "a missed amendment, a veto or a misread",
    "target_not_read": "no stage read the target item (its law isn't downloaded or predates the "
    "Legislature's API)",
}
RESTATE_TOLERANCE = 0.01  # Q27: the same law's §2 adds an amount within 1% of the change


def _law_order(law_key: str) -> tuple[int, int]:
    year, chapter = law_key.split("-")
    return int(year), int(chapter)


def _section_order(section: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(.*)", section)
    return (int(m[1]), m[2]) if m else (10**9, section)


def _int(value: str | None) -> int | None:
    return int(value) if value else None


def _figures(text: str) -> set[int]:
    """Dollar figures in an item's text, read the way read_amendments reads a struck figure, so a
    misprint such as "$15,000,0000" (2021-102 item 1599-2026) is found as 150,000,000."""
    return {int(f.replace(",", "")) for f in re.findall(r"\$\s*(\d[\d,]*)", text)}


def amendment_amounts(
    items: list[dict[str, str]], amendments: list[dict[str, str]], laws: list[dict[str, str]]
) -> list[dict]:
    """Each item's running amount before and after every amendment that changes it (§5.5).

    ``items`` are items_raw and bond_items_raw rows, ``amendments`` amendments_raw rows and
    ``laws`` law_list rows. An item starts at the amount printed in the law that created it (its
    retained-revenue ceiling if it has no amount). Amendments are applied in approval-date order,
    then section order within a law. ``change`` is what happened to the item's figure; whether it
    counts toward the totals is decided when the funding actions are built (§10, Q21, Q27).
    """
    law = {r["law_key"]: r for r in laws}
    amount: dict[tuple[str, str, str], int | None] = {}
    text: dict[tuple[str, str, str], str] = {}
    supplement: dict[tuple[str, str, str], int] = {}  # (law, item, FY) -> a §2… amount (Q27)
    for r in items:
        key = (r["law_key"], r["section"], r["line_item"])
        if key not in amount:
            amount[key] = _int(r["amount"] or r["retained_revenue_ceiling"])
            text[key] = r["item_text"]
        if r["amount"] and r["fy_stated"]:
            supplement.setdefault((r["law_key"], r["line_item"], r["fy_stated"]), int(r["amount"]))
    # A law sometimes names the wrong section: 2019-142 §48 strikes 1595-1068 from "section 2"
    # of the FY2020 GAA, which prints it in §2E. Use the item's only section in that law, if any.
    sections: dict[tuple[str, str], set[str]] = {}
    for law_key, section, item in amount:
        sections.setdefault((law_key, item), set()).add(section)

    order = sorted(
        (a for a in amendments if a["action_type"] in AMOUNT_ACTIONS and a["target_item"]),
        key=lambda a: (
            law.get(a["law_key"], {}).get("approved_date", ""),
            _law_order(a["law_key"]),
            _section_order(a["section"]),
        ),
    )
    out = []
    for a in order:
        kind, key = a["action_type"], (a["target_law_key"], a["target_section"], a["target_item"])
        found = sections.get((key[0], key[2]), set())
        if key not in amount and len(found) == 1:
            key = (key[0], next(iter(found)), key[2])
        before = amount.get(key)
        known = before is not None
        old, new = _int(a["old_figure"]), _int(a["new_figure"])
        check, note = "", ""
        if kind == "figure_change":
            if not known:
                # whether the figure is the item's total is unknown, so its amount stays unknown
                check, after = "target_not_read", None
            elif before == old:
                check, after = "match", new
            elif before == new:
                check, after = "already_new", before
            elif old in _figures(text.get(key, "")):
                check, after = "in_item_text", before
            else:
                check, after = "mismatch", new
            change = after - before if check in ("match", "already_new", "in_item_text") else None
            if change is None and old is not None and new is not None:
                change = new - old  # the law's own change, when the running amount isn't trusted
        elif kind == "item_strike":
            after = 0
            change = -before if known else None
        else:  # item_insert, item_replace
            after = new
            if kind == "item_insert" and key in amount:
                note = "the item already exists; check whether this replaces it"
            base = 0 if kind == "item_insert" and not known else before
            change = new - base if new is not None and base is not None else None
            text[key] = a["source_text"]
        if change is None and not check:
            check = "target_not_read"
        if check == "target_not_read" and law.get(key[0], {}).get("parse_strategy") == "manual":
            note = "the target law is kept by hand (review/sources/): a person works out the change"
        amount[key] = after

        fy = law.get(a["target_law_key"], {}).get("primary_fy", "")
        added = supplement.get((a["law_key"], a["target_item"], fy))
        if (
            added
            and change
            and a["law_key"] != a["target_law_key"]
            and abs(added - change) <= RESTATE_TOLERANCE * abs(change)
        ):
            note = (
                f"this law's §2 also adds ${added:,} to the item for FY{fy}: probably the same "
                "money (Q27)"
            )
        out.append(
            {
                **{c: a[c] for c in AMOUNT_COLUMNS[:8]},
                "amount_before": before,
                "amount_after": after,
                "change": change,
                "check": check,
                "review": "true" if check not in ("", "match") or note else "false",
                "note": note,
            }
        )
    return out


# -- Bond rows (workstream A; DESIGN §7.7, §7.16, §10; decisions of 2026-11-06) ----------------

# The reader's veto note (§7.3) -> veto_status (§9.9). A whole-item veto is left out instead (a
# pocket veto has no amount), so "disapproved" only reaches here as a wording note on an item
# whose amount stands, before read_items labels those wording_vetoed (PR #30): unknown until then.
BOND_VETO_STATUS = {
    "none": "none",
    "reduced": "reduced",
    "reduced_and_wording": "reduced",
    "overridden": "overridden",
    "wording_vetoed": "wording_vetoed",
    "disapproved": "unknown",
}


def enactment_fy(approved: str) -> int:
    """The fiscal year containing a date: FY2025 runs July 1, 2024 to June 30, 2025 (§5.4)."""
    d = date.fromisoformat(approved)
    return d.year + 1 if d.month >= 7 else d.year


def limit_for(row: Mapping[str, str], limits: list[Mapping[str, str]]) -> Mapping[str, str] | None:
    """The borrowing limit (bond_authorizations_raw row, §7.16) covering a bond item: one that
    names the item (2021-15 §6 covers only 4000-2026), else one that covers its section."""
    same_law = [lim for lim in limits if lim["law_key"] == row["law_key"]]
    for lim in same_law:
        if row["line_item"] in lim["covers_items"].split(";"):
            return lim
    for lim in same_law:
        if not lim["covers_items"] and row["section"] in lim["covers_sections"].split(";"):
            return lim
    return None


def bond_rows(
    bond_items: list[Mapping[str, str]],
    limits: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    session_law_url: str,
) -> list[dict[str, Any]]:
    """Funding-action rows (§7.7) for the bond items of in-scope laws, in source order.

    Each is a capital authorization (``CAP``), never counted in operating totals (Q5). Items that
    never became law (pocket-vetoed: no amount) and reference-only laws' items are left out. An item
    under a limit with an identified federal share gets ``federal_share`` = that share over the
    limit's items (New 1). Restated items (New 2) come through the amendment rows, not here.
    """
    laws = {r["law_key"]: r for r in law_list}
    out = []
    for item in bond_items:
        law = laws.get(item["law_key"])
        if not law or law["role"] != "in_scope" or not item["amount"]:
            continue
        limit = limit_for(item, limits) or {}
        share = ""
        if limit.get("federal_split") == "identified" and int(limit["items_total"] or 0):
            share = int(limit["federal_share"]) / int(limit["items_total"])  # exact: no rounding
        veto = item["veto_kind_inline"] or "none"
        flags = []
        if share:
            flags += ["federal"] + (["federal_mixed"] if share < 1 else [])
        if veto != "none":
            flags.append("veto_unverified")  # no CTHRU data for bonds (§5.7)
        if item["confidence"] == "low":
            flags.append("low_confidence_parse")
        out.append(
            {
                "law_key": item["law_key"],
                "section": item["section"],
                "line_item": item["line_item"],
                "target_law_key": item["law_key"],
                "event_date": law["approved_date"],
                "calendar_year": int(law["approved_date"][:4]),
                "fiscal_year": enactment_fy(law["approved_date"]),
                "fy_rule": "enactment_fy",
                "available_through": limit.get("available_through", ""),
                "section_type": "capital",
                "funding_action": "CAP",
                "amount_kind": "bond_authorization",
                "amount": int(item["amount"]),
                "amount_source": "law_text",
                "amount_printed": int(item["amount_struck"] or item["amount"]),
                "veto_status": BOND_VETO_STATUS.get(veto, "unknown"),
                "counts_toward_total": "false",
                "fund_primary": "",
                "federal_share": share,
                "flags": ";".join(flags),
                "agency_header_raw": item["agency_header_raw"],
                "item_text": item["item_text"],
                "source_url": session_law_url.format(
                    acts_year=law["acts_year"], chapter=law["chapter"]
                ),
                "source_para_start": item["para_start"],
                "reader_version": item["reader_version"],
            }
        )
    prefixes = [
        schemas.record_id_prefix(
            int(laws[r["law_key"]]["acts_year"]),
            laws[r["law_key"]]["chapter"],
            r["section"],
            r["line_item"],
            "CAP",
        )
        for r in out
    ]
    for r, record_id in zip(out, schemas.assign_record_ids(prefixes), strict=True):
        r["record_id"] = record_id
    return [{c: r[c] for c in schemas.columns("funding_actions")} for r in out]


def capital_total(rows: list[Mapping[str, Any]]) -> int:
    """The capital total (New 1): bond amounts minus identified federal shares."""
    total = 0
    for r in rows:
        if r["funding_action"] != "CAP":
            continue
        share = float(r["federal_share"] or 0)
        total += round(int(r["amount"]) * (1 - share))
    return total


def run(ctx: Context) -> int:
    raise NotImplementedError
