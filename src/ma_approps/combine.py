"""Stage 6 `combine`: build funding_actions.csv, fund_splits.csv, running_amounts.csv (DESIGN §5,
§7.6–§7.8).

A owns the shared core (decided 2026-11-10): it collects each piece's rows, keeps in-scope
laws, assigns Record IDs, decides counts_toward_total and splits rows by fund. GAA rows come from
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
- Any other GAA item in a section CTHRU covers (approp_main, trust_transfer, surtax) with no CTHRU
  amount was vetoed to $0 (veto_status = vetoed); don't fall back to the printed amount. FY2025's
  law text doesn't mark its vetoes. Apply this only after the two cases above, never to §2D.
- CTHRU fund 0015 is §2B ISF chargebacks: counts_toward_total = false, even though CTHRU gives
  them non-zero fee-revenue caps ($632–704M a year).
"""

import csv
import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = True

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


def item_sections(items: list[Mapping[str, str]]) -> dict[tuple[str, str], set[str]]:
    """(law, line item) -> the sections that print it."""
    sections: dict[tuple[str, str], set[str]] = {}
    for r in items:
        sections.setdefault((r["law_key"], r["line_item"]), set()).add(r["section"])
    return sections


def target_section(a: Mapping[str, str], sections: Mapping[tuple[str, str], set[str]]) -> str:
    """The section of the target law that holds the amended item. A law sometimes names the wrong
    one: 2019-142 §48 strikes 1595-1068 from "section 2" of the FY2020 GAA, which prints it in
    §2E. Then the item's only section in that law is used, if it has one."""
    found = sections.get((a["target_law_key"], a["target_item"]), set())
    if a["target_section"] not in found and len(found) == 1:
        return next(iter(found))
    return a["target_section"]


def manual_items(rows: list[Mapping[str, str]]) -> list[dict[str, str]]:
    """``config/manual_rows.csv`` rows (§7.6) as items with a starting amount, for laws no stage
    reads: 1993-52, kept by hand, prints item 4000-8200 at $50,000,000, which 2024-150 §60 restates
    (issue #41). Only rows for the law's own items (``target_law_key`` = ``law_key``)."""
    return [
        {
            "law_key": r["law_key"],
            "section": r["section"],
            "line_item": r["line_item"],
            "amount": r["amount"],
            "retained_revenue_ceiling": "",
            "item_text": r["item_text"],
            "fy_stated": "",
        }
        for r in rows
        if r["line_item"] and r["amount"] and r["target_law_key"] in ("", r["law_key"])
    ]


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
    sections = item_sections(items)

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
        if key not in amount:  # not printed there, nor inserted there by an earlier amendment
            key = (key[0], target_section(a, sections), key[2])
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


# -- Amendment rows (workstream C; DESIGN §5.4, §5.5, §7.7, §10, §11.3; issue #41) -------------

# Actions whose funding action doesn't depend on an amount: action_type -> (funding_action,
# amount_kind). The amount actions (AMOUNT_ACTIONS) are worked out from the running amounts.
AMENDMENT_ACTIONS = {
    "text_insert": ("PURP", "none"),
    "text_strike": ("PURP", "none"),
    "purpose_change": ("PURP", "none"),
    "date_extend": ("REAUTH", "none"),
    "transfer": ("XFER", "transfer"),
    "direct_appropriation": ("NEW", "appropriation"),
}
# What the amended item is, from its section in the target law (§9.4), so an amendment counts the
# way the item does (§10): a change to a §2B chargeback, a §2D federal grant or a §2E trust
# transfer doesn't count. Any other section, or no item: an outside section.
TARGET_SECTION_TYPES = {
    "2": ("approp_main", ()),
    "2A": ("approp_new", ()),
    "2B": ("isf", ("isf_chargeback",)),
    "2D": ("federal_grants", ("federal",)),
    "2E": ("trust_transfer", ("trust_transfer",)),
    "2F": ("surtax", ()),
}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _amount_key(a: Mapping[str, Any]) -> tuple:
    return tuple(str(a[c] or "") for c in AMOUNT_COLUMNS[:8])


def _change(kind: str, a: Mapping[str, str], amount: Mapping[str, Any] | None) -> tuple:
    """(funding_action, amount_kind, amount, low confidence) for an amount action (§11.3), from its
    running amount (``amendment_amounts``).

    - A figure change raises (``INC``) or cuts (``RED``) the item by its change. It counts $0 when
      it doesn't change the item's amount: the struck figure is a cap or earmark in the item's text,
      or the item already shows the new figure (Q21), or this law's §2 adds the same money (Q27).
      When the running amount isn't known or doesn't match, the law's own change is used and the
      row is sent to review.
    - An inserted item is new money (``NEW``); a struck item is cut by its running amount (``RED``).
    - A replaced item changes by the new amount less the running amount. At the same amount only
      its wording changes (``PURP``, $0; Q26 option 1).
    """
    check = amount["check"] if amount else "target_not_read"
    change = amount["change"] if amount else None
    low = check in ("mismatch", "target_not_read") or change is None
    if kind == "figure_change":
        old, new = _int(a["old_figure"]), _int(a["new_figure"])
        action = "RED" if old is not None and new is not None and new < old else "INC"
        if check in ("in_item_text", "already_new") or "Q27" in (amount or {}).get("note", ""):
            return action, "delta", 0, False
        return action, "delta", change, low
    if kind == "item_insert":
        return "NEW", "appropriation", change, low
    if kind == "item_strike":
        return "RED", "delta", change, low
    if change == 0:
        return "PURP", "none", 0, False
    return ("RED" if change is not None and change < 0 else "INC"), "delta", change, low


def _bond_available_through(
    a: Mapping[str, str], section: str, limits: list[Mapping[str, str]]
) -> str:
    """A changed bond item's spending end date: from the amending law's borrowing limit for the
    amending section, if it has one, else from the item's own limit (issue #41)."""
    for lim in limits:
        if lim["law_key"] == a["law_key"] and a["section"] in lim["covers_sections"].split(";"):
            return lim["available_through"]
    item = {"law_key": a["target_law_key"], "section": section, "line_item": a["target_item"]}
    return (limit_for(item, limits) or {}).get("available_through", "")


def amendment_rows(
    amendments: list[Mapping[str, str]],
    amounts: list[Mapping[str, Any]],
    items: list[Mapping[str, str]],
    limits: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    session_law_url: str,
    cthru: list[Mapping[str, str]] = (),
) -> list[dict[str, Any]]:
    """Funding-action rows (§7.7) for what in-scope laws' outside sections do (amendments_raw),
    in source order (Combine-Export-Work-Split.md, C).

    - The funding action follows §11.3 (``AMENDMENT_ACTIONS``, ``_change``). An amount comes from
      the item's running amount (``amendments`` -> ``amounts``, §5.5), so a replaced item counts
      only its change.
    - A change to an existing item takes the fiscal year of the act it amends (§5.4,
      ``fy_rule = target_act``) and counts the way that item does (``TARGET_SECTION_TYPES``). When
      that act has no single fiscal year (a surplus law), it takes the amending law's own year
      (``stated``), else the approval's (Q28).
    - A change to a **bond** item is a capital authorization: ``CAP`` by the change, never counted
      (Q5, issue #41); its wording changes are ``PURP``. Bond-item rows use the amending law's
      fiscal year, like bond rows.
    - Transfers and direct appropriations take the fiscal year of the law's approval; an interim
      budget is ``INT``. A transfer's line item is the item it goes to, else the one it comes from.
      Money moved from a fund into an item is an ``INC`` to that item, flagged
      ``fund_transfer_chain``, and counts: it is the appropriation out of the fund (Q24).
    - A date extension's new date, when it is a whole date, is ``available_through``.
    - Fund: a transfer's is the one fund it comes from. A change to an operating item takes the
      item's fund as supplemental items do: the law's printed split, else the one fund CTHRU books
      the item to that year, else the item's section fund (Q33: 2022-42 §47 adds $24,000,000 to
      1599-2026, which CTHRU books to the federal Fund 2005, so the row is federal).
    - Reference-only laws' amendments are left out: they are read only for items' history (§1).
    """
    laws = {r["law_key"]: r for r in law_list}
    sections = item_sections(items)
    by_item = {(i["law_key"], i["section"], i["line_item"]): i for i in items}
    cthru_funds = _cthru_funds(cthru)
    pending: dict[tuple, list[Mapping[str, Any]]] = {}
    for r in amounts:
        pending.setdefault(_amount_key(r), []).append(r)
    out = []
    for a in amendments:
        law = laws.get(a["law_key"])
        if not law or law["role"] != "in_scope":
            continue
        kind = a["action_type"]
        has_target = bool(a["target_item"] or a["target_law_key"]) and kind not in (
            "transfer",
            "direct_appropriation",
        )
        target = laws.get(a["target_law_key"], {}) if has_target else law
        bond = has_target and target.get("law_type") == "bond"
        section = target_section(a, sections) if a["target_item"] else a["target_section"]
        flags = ["low_confidence_parse"] if a["confidence"] == "low" else []
        available = ""
        line_item = a["target_item"]
        if kind in AMOUNT_ACTIONS and a["target_item"]:
            queue = pending.get(_amount_key(a))
            action, amount_kind, amount, low = _change(kind, a, queue.pop(0) if queue else None)
            if low and "low_confidence_parse" not in flags:
                flags.append("low_confidence_parse")
        else:
            action, amount_kind = AMENDMENT_ACTIONS.get(kind, ("PURP", "none"))
            amount = _int(a["amount"]) if kind in ("transfer", "direct_appropriation") else None
            if kind == "date_extend" and ISO_DATE_RE.match(a["new_date"] or ""):
                available = a["new_date"]
            if kind == "transfer":
                line_item = a["to_item"] or a["from_item"]
                if a["to_item"] and not a["from_item"] and a["fund_raw"]:
                    # money moved from a fund into a line item is the appropriation out of that
                    # fund, so it counts (Q24: 2024-88 §25, Transitional Escrow Fund to 1599-0514)
                    action, amount_kind = "INC", "delta"
                    flags.append("fund_transfer_chain")
        if kind == "direct_appropriation" and law["law_type"] == "interim":
            action, amount_kind = "INT", "interim"
        if bond:
            section_type = "capital"
            # every change to a bond item's amount, $0 included (a restated item), is a capital
            # authorization; a wording change stays PURP (issue #41; the $0 label waits on Q26)
            if kind in AMOUNT_ACTIONS or action != "PURP":
                action, amount_kind = "CAP", "bond_authorization"
            available = available or _bond_available_through(a, section, limits)
        elif has_target and line_item:
            section_type, section_flags = TARGET_SECTION_TYPES.get(section, ("outside", ()))
            flags += [f for f in section_flags if f not in flags]
        else:
            section_type = "interim" if action == "INT" else "outside"
        if bond or not has_target:
            fy, fy_rule = enactment_fy(law["approved_date"]), "enactment_fy"
            if action == "INT" and law.get("primary_fy"):
                fy, fy_rule = int(law["primary_fy"]), "stated"
        elif target.get("primary_fy"):
            fy, fy_rule = int(target["primary_fy"]), "target_act"
        elif law.get("primary_fy"):
            # the amended act has no single fiscal year (a surplus law): the amending budget's own
            # year, as CTHRU books it (2023-77 §167 adds $4,000,000 to 2022-268's 1599-6063: FY2023)
            fy, fy_rule = int(law["primary_fy"]), "stated"
        else:
            fy, fy_rule = enactment_fy(law["approved_date"]), "enactment_fy"
        if available and "multi_year" not in flags:
            flags.append("multi_year")
        funds = [f for f in (a["fund_raw"] or "").split("; ") if f]
        # fund splits (shared core): the one fund the money comes from, if the law names one;
        # else, for an operating item, the item's own fund (Q33)
        fund = {"section_fund_default": funds[0] if len(funds) == 1 else ""}
        if line_item and not bond and not funds and kind != "transfer":
            item = by_item.get((a["target_law_key"] or a["law_key"], section, line_item), {})
            if item.get("fund_splits_raw"):
                fund["fund_splits_raw"] = item["fund_splits_raw"]
            elif (str(fy), line_item) in cthru_funds:
                fund["fund_numbers"] = cthru_funds[(str(fy), line_item)]
            else:
                fund["section_fund_default"] = item.get("section_fund_default", "")
        out.append(
            {
                "law_key": a["law_key"],
                "section": a["section"],
                "line_item": line_item,
                "target_law_key": a["target_law_key"] if has_target else a["law_key"],
                "event_date": law["approved_date"],
                "calendar_year": int(law["approved_date"][:4]),
                "fiscal_year": fy,
                "fy_rule": fy_rule,
                "available_through": available,
                "section_type": section_type,
                "funding_action": action,
                "amount_kind": amount_kind,
                "amount": "" if amount is None else amount,
                "amount_source": "law_text",
                "veto_status": "none",
                "federal_share": 1.0 if section_type == "federal_grants" else "",
                "flags": ";".join(flags),
                "item_text": a["source_text"],
                "source_url": session_law_url.format(
                    acts_year=law["acts_year"], chapter=law["chapter"]
                ),
                "reader_version": a["reader_version"],
                **fund,
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
    return [{c: r.get(c, "") for c in schemas.columns("funding_actions")} for r in out]


def capital_total(rows: list[Mapping[str, Any]]) -> int:
    """The capital total (New 1): bond amounts minus identified federal shares."""
    total = 0
    for r in rows:
        # an amendment of a bond item whose amount isn't known yet has none (2024-150 §60)
        if r["funding_action"] != "CAP" or r["amount"] in ("", None):
            continue
        share = float(r["federal_share"] or 0)
        total += round(int(r["amount"]) * (1 - share))
    return total


# -- Supplemental rows and §2D federal grant rows (workstream B; DESIGN §7.7, §10) -------------

SUPPLEMENTAL_LAW_TYPES = ("supplemental", "surplus", "other")

# What each section of a supplemental budget is, from its own preamble (2021-29, 2023-77, …):
# section -> (section_type, funding_action, amount_kind, flags)
SUPPLEMENTAL_SECTIONS = {
    # "To provide for supplementing certain items in the general appropriation act …"
    "2": ("approp_main", "INC", "delta", ()),
    # "To provide for certain unanticipated obligations of the commonwealth …"
    "2A": ("approp_new", "NEW", "appropriation", ()),
    # "To provide for supplementing certain intragovernmental chargeback authorizations …"
    "2B": ("isf", "INC", "delta", ("isf_chargeback",)),
    # "… balances of appropriations which otherwise would revert … are hereby re-appropriated"
    "2CI": ("prior_approp", "PAC", "prior_appropriation_continued", ()),
    # "… balances of retained revenue and intragovernmental chargeback authorizations … are
    # hereby re-authorized"
    "2CII": ("prior_approp", "REAUTH", "prior_appropriation_continued", ()),
    "2D": ("federal_grants", "NEW", "appropriation", ()),
    # "… hereby appropriated for transfer from the General Fund to the trust funds …" (Q2)
    "2E": ("trust_transfer", "NEW", "appropriation", ("trust_transfer",)),
    "2F": ("surtax", "INC", "delta", ()),
}
# Any other section: read as new money, flagged for review
OTHER_SECTION = ("approp_new", "NEW", "appropriation", ("low_confidence_parse",))

# The reader's veto note (§7.3) -> veto_status (§9.9). Vetoes in supplementals can't be checked
# against CTHRU (it has no per-law amounts), so any veto is also flagged veto_unverified (§5.7).
SUPPLEMENTAL_VETO_STATUS = {
    "none": "none",
    "reduced": "reduced",
    "reduced_and_wording": "reduced",
    "overridden": "overridden",
    "wording_vetoed": "wording_vetoed",
    "disapproved": "vetoed",
}

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
# "… shall be made available for the purposes of this item until June 30, 2025"
AVAILABLE_UNTIL_RE = re.compile(
    rf"\bavailable\b[^.;]{{0,200}}?\b(?:until|through) ((?:{MONTHS}) \d{{1,2}}, \d{{4}})"
)


def available_through(item_text: str, fiscal_year: int) -> str:
    """The date an item's money stays available until, if the text gives one past the fiscal
    year's end (§5.4); else ""."""
    dates = [
        datetime.strptime(d, "%B %d, %Y").date() for d in AVAILABLE_UNTIL_RE.findall(item_text)
    ]
    later = [d for d in dates if d > date(fiscal_year, 6, 30)]
    return max(later).isoformat() if later else ""


def _cthru_funds(cthru: list[Mapping[str, str]]) -> dict[tuple[str, str], str]:
    """(fiscal year, line item) -> CTHRU's fund number, where CTHRU books the item to one fund."""
    out = {}
    for r in cthru:
        numbers = [n for n in r["fund_numbers"].split(";") if n]
        if len(numbers) == 1:
            out[(r["fiscal_year"], r["line_item"])] = numbers[0]
    return out


def _items_row(
    item: Mapping[str, str], law: Mapping[str, str], session_law_url: str
) -> dict[str, Any]:
    """The fields every row built from an items_raw row shares (§7.3 -> §7.7)."""
    fy = int(item["fy_stated"]) if item["fy_stated"] else enactment_fy(law["approved_date"])
    return {
        "law_key": item["law_key"],
        "section": item["section"],
        "line_item": item["line_item"],
        "target_law_key": item["law_key"],
        "event_date": law["approved_date"],
        "calendar_year": int(law["approved_date"][:4]),
        "fiscal_year": fy,
        "fy_rule": "stated" if item["fy_stated"] else "enactment_fy",
        "available_through": available_through(item["item_text"], fy),
        "amount_source": "law_text",
        "amount_printed": int(item["amount_struck"] or item["amount"] or 0),
        "agency_header_raw": item["agency_header_raw"],
        "item_text": item["item_text"],
        "source_url": session_law_url.format(acts_year=law["acts_year"], chapter=law["chapter"]),
        "source_para_start": item["para_start"],
        "reader_version": item["reader_version"],
        # fund splits (shared core): the law's printed split, else the section's fund
        "fund_splits_raw": item["fund_splits_raw"],
        "section_fund_default": item["section_fund_default"],
    }


def supplemental_rows(
    items: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    cthru: list[Mapping[str, str]],
    session_law_url: str,
) -> list[dict[str, Any]]:
    """Funding-action rows (§7.7) for the items of in-scope supplemental, surplus and other laws,
    in source order (Combine-Export-Work-Split.md, B).

    - Each section's action comes from its preamble (``SUPPLEMENTAL_SECTIONS``). §2 adds "to any
      amounts previously appropriated", so its items are increases (``INC``) of items that already
      exist: in that fiscal year's GAA, in any law approved earlier (any section or year, e.g.
      2022-268 §2 adding to 1599-0793, which 2022-42 §2A created), or in CTHRU (that year's
      original budget, or any amount in an earlier year). An item that exists nowhere yet is new
      money: ``NEW`` (Emma's review of #46).
    - Amounts are the law's (``amount_source = law_text``); a whole-item veto gives $0.
    - Fund: the law's printed split; else the one fund CTHRU books the item to that year (2021-102
      §2A names two funds, ARPA and the Transitional Escrow Fund, without saying which item uses
      which); else the section's fund.
    - Reference-only laws' items are left out (§1).
    """
    laws = {r["law_key"]: r for r in law_list}
    budgeted = {(r["fy_stated"], r["line_item"]) for r in items if _law_type(laws, r) == "gaa"}
    budgeted |= {
        (r["fiscal_year"], r["line_item"]) for r in cthru if int(r["original_enacted"] or 0)
    }
    budget_years = {fy for fy, _ in budgeted}
    # When each item first appears in a law (approval date), and in CTHRU (fiscal year)
    first_law: dict[str, str] = {}
    for r in items:
        approved = laws.get(r["law_key"], {}).get("approved_date", "")
        if approved and approved < first_law.get(r["line_item"], "9999"):
            first_law[r["line_item"]] = approved
    first_cthru: dict[str, int] = {}
    for r in cthru:
        if int(r["total_enacted"] or 0):
            fy_ = int(r["fiscal_year"])
            first_cthru[r["line_item"]] = min(fy_, first_cthru.get(r["line_item"], fy_))
    funds = _cthru_funds(cthru)

    def existed(line_item: str, fy: str, approved: str) -> bool:
        return (
            (fy, line_item) in budgeted
            or first_law.get(line_item, "9999") < approved
            or first_cthru.get(line_item, 9999) < int(fy)
        )

    out = []
    for item in items:
        law = laws.get(item["law_key"])
        if not law or law["role"] != "in_scope" or law["law_type"] not in SUPPLEMENTAL_LAW_TYPES:
            continue
        section_type, action, kind, section_flags = SUPPLEMENTAL_SECTIONS.get(
            item["section"], OTHER_SECTION
        )
        row = _items_row(item, law, session_law_url)
        fy = str(row["fiscal_year"])
        if (
            action == "INC"
            and fy in budget_years
            and not existed(item["line_item"], fy, law["approved_date"])
        ):
            action, kind = "NEW", "appropriation"  # the item doesn't exist yet: a new item
        veto = item["veto_kind_inline"] or "none"
        amount = int(item["amount"] or 0)  # "": the whole amount is struck (vetoed)
        flags = list(section_flags)
        if row["available_through"]:
            flags.append("multi_year")
        if veto != "none":
            flags.append("veto_unverified")
        if item["confidence"] == "low" and "low_confidence_parse" not in flags:
            flags.append("low_confidence_parse")
        if not item["fund_splits_raw"] and (fy, item["line_item"]) in funds:
            row["fund_numbers"] = funds[(fy, item["line_item"])]
        row.update(
            section_type=section_type,
            funding_action=action,
            amount_kind=kind,
            amount=amount,
            veto_status=SUPPLEMENTAL_VETO_STATUS.get(veto, "unknown"),
            flags=";".join(flags),
        )
        out.append(row)
    return out


def federal_grant_rows(
    items: list[Mapping[str, str]], law_list: list[Mapping[str, str]], session_law_url: str
) -> list[dict[str, Any]]:
    """Funding-action rows (§7.7) for the §2D federal grant items of in-scope GAAs, in source
    order (Combine-Export-Work-Split.md, B; Mario's rules at the top of this file).

    CTHRU has no §2D items, so the amount is the law's printed one (``amount_source = law_text``).
    The money is federal (Q1): ``federal_share`` 1, flagged ``federal``, never counted. CTHRU can't
    confirm vetoes here, so ``veto_status = unknown`` and ``veto_unverified``.
    """
    laws = {r["law_key"]: r for r in law_list}
    out = []
    for item in items:
        law = laws.get(item["law_key"])
        if not law or law["role"] != "in_scope" or law["law_type"] != "gaa":
            continue
        if item["section"] != "2D":
            continue
        row = _items_row(item, law, session_law_url)
        flags = ["federal", "veto_unverified"]
        if row["available_through"]:
            flags.append("multi_year")
        if item["confidence"] == "low":
            flags.append("low_confidence_parse")
        row.update(
            section_type="federal_grants",
            funding_action="ORIG",
            amount_kind="appropriation",
            amount=int(item["amount"] or 0),
            veto_status="unknown",
            federal_share=1.0,
            flags=";".join(flags),
        )
        out.append(row)
    return out


# -- Annual budget rows (workstream E; DESIGN §3.4, §5.7, §10; Mario's rules at the top) ---------

# What each GAA section is (§9.4): section -> (section_type, flags, CTHRU covers its amounts).
# §2D is left to federal_grant_rows. CTHRU shows §2B at $0 (§3.4), so those take the law's printed
# amount. It does carry §2E (trust transfers, e.g. 1595-0035; $2.06B in FY2024), which is flagged
# and not counted (§10).
ANNUAL_SECTIONS = {
    "2": ("approp_main", (), True),
    "2B": ("isf", ("isf_chargeback",), False),
    "2E": ("trust_transfer", ("trust_transfer",), True),
    "2F": ("surtax", (), True),
}
ANNUAL_OTHER_SECTION = ("approp_new", ("low_confidence_parse",), False)
ANNUAL_SKIPPED_SECTIONS = ("2D",)
CHARGEBACK_FUND = "0015"  # §2B ISF chargebacks (config/funds.csv): never counted


def _annual_veto_status(hint: str, final: int, printed: int, cthru_amount: int) -> tuple[str, bool]:
    """(veto_status, unexplained difference) for a GAA item CTHRU has money for (§5.7).

    ``final`` is the law's last printed amount (after any veto note), ``printed`` the first
    (before it). CTHRU agreeing with the final amount confirms what the markup says. CTHRU below
    the printed amount with no markup is a veto the law text doesn't show (FY2025's doesn't
    mark them), so it is read from CTHRU. An override with CTHRU above the printed (reduced)
    figure is the Legislature restoring money. Any other difference, such as 1231-1000 (override
    printed at $10M, CTHRU $1.5M), is unexplained and goes to review.
    """
    marked = SUPPLEMENTAL_VETO_STATUS.get(hint, "unknown")
    if cthru_amount == final:
        return marked, False
    if hint == "none" and cthru_amount < printed:
        return "reduced", False
    if hint == "overridden" and cthru_amount > final:
        # The law text prints the Governor's reduced figure and CTHRU the amount after the
        # Legislature restored money (3000-5000: printed $16.5M, CTHRU $17.5M). Whether all of the
        # cut came back (overridden) or part of it (partial_override, Q13) needs the pre-veto
        # figure, which items_raw doesn't keep for these items.
        return "overridden", False
    return marked, True


def _gaa_items(
    items: list[Mapping[str, str]], law_list: list[Mapping[str, str]], with_skipped: bool = False
) -> list[tuple[Mapping[str, str], Mapping[str, str]]]:
    """(item, law) for the items of in-scope GAAs, leaving §2D to federal_grant_rows unless
    ``with_skipped``."""
    laws = {r["law_key"]: r for r in law_list}
    return [
        (item, laws[item["law_key"]])
        for item in items
        if item["law_key"] in laws
        and laws[item["law_key"]]["role"] == "in_scope"
        and laws[item["law_key"]]["law_type"] == "gaa"
        and (with_skipped or item["section"] not in ANNUAL_SKIPPED_SECTIONS)
    ]


def _annual_fy(item: Mapping[str, str], law: Mapping[str, str]) -> str:
    """The fiscal year of a GAA item: every item of a GAA belongs to the law's own year (the law
    list's ``primary_fy``). The reader's ``fy_stated`` is only the fallback: it says FY2021 for the
    36 §2B items of 2021-24, whose text says "fiscal year ending June 30, 2022" (Emma's review of
    PR #48)."""
    return law.get("primary_fy") or item["fy_stated"]


def annual_rows(
    items: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    cthru: list[Mapping[str, str]],
    session_law_url: str,
) -> list[dict[str, Any]]:
    """Original-appropriation rows (``ORIG``, §7.7) for the items of in-scope GAAs, in source
    order (Combine-Export-Work-Split.md, E; Mario's rules at the top of this file).

    - In a section CTHRU covers (§2, §2E, §2F), the amount is CTHRU's ``original_enacted`` for that
      fiscal year and item (``amount_source = cthru``), which already reflects vetoes; the law's
      printed amount stays in ``amount_printed``. ``veto_status`` comes from comparing the two,
      with the inline markup as a hint (``_annual_veto_status``).
    - No CTHRU amount, and the item lets an agency spend fees it collects: the law's printed ceiling
      (``retained_revenue_ceiling``, flag ``retained_revenue``). Otherwise it was vetoed to $0.
    - §2B items take the law's printed amount and are flagged ``isf_chargeback``; an item CTHRU
      books only to fund 0015 is flagged the same wherever it is printed (§10). §2E items are
      flagged ``trust_transfer``. Neither counts toward the total.
    - A row's fiscal year is the law's own (``primary_fy``), not the reader's ``fy_stated``
      (``_annual_fy``).
    - CTHRU has one amount per account, so an item printed twice in a law gets it once; both rows
      are flagged ``cthru_mismatch``. A fiscal year with no CTHRU rows at all (not downloaded yet)
      falls back to the printed amount, flagged ``cthru_mismatch``, instead of reading as vetoed.
    """
    by_cthru = {(r["fiscal_year"], r["line_item"]): r for r in cthru}
    cthru_years = {r["fiscal_year"] for r in cthru}
    gaa_items = _gaa_items(items, law_list)
    copies: dict[tuple[str, str, str], int] = {}
    for item, law in gaa_items:
        if ANNUAL_SECTIONS.get(item["section"], ANNUAL_OTHER_SECTION)[2]:  # CTHRU's one amount
            key = (item["law_key"], _annual_fy(item, law), item["line_item"])
            copies[key] = copies.get(key, 0) + 1
    used: set[tuple[str, str, str]] = set()
    out = []
    for item, law in gaa_items:
        section_type, section_flags, covered = ANNUAL_SECTIONS.get(
            item["section"], ANNUAL_OTHER_SECTION
        )
        row = _items_row(item, law, session_law_url)
        fy = _annual_fy(item, law)
        if fy:
            row["fiscal_year"], row["fy_rule"] = int(fy), "stated"
            row["available_through"] = available_through(item["item_text"], int(fy))
        flags = list(section_flags)
        hint = item["veto_kind_inline"] or "none"
        final = int(item["amount"] or 0)
        printed = int(item["amount_struck"] or item["amount"] or 0)
        ceiling = int(item["retained_revenue_ceiling"] or 0)
        status = SUPPLEMENTAL_VETO_STATUS.get(hint, "unknown")
        source, kind = "law_text", "appropriation"
        match = by_cthru.get((fy, item["line_item"]))
        key = (item["law_key"], fy, item["line_item"])
        if covered and copies[key] > 1:
            flags.append("cthru_mismatch")
        if covered and fy in cthru_years:
            original = int(match["original_enacted"] or 0) if match else 0
            if key in used:  # CTHRU's one amount went to this item's first copy
                amount, source, status = 0, "cthru", "unknown"
            elif original:
                used.add(key)
                amount, source = original, "cthru"
                status, unexplained = _annual_veto_status(hint, final, printed, original)
                if unexplained:
                    flags.append("cthru_mismatch")
                if ceiling:
                    flags.append("retained_revenue")
            elif ceiling:
                used.add(key)
                amount, kind = ceiling, "retained_revenue_ceiling"
                flags += ["retained_revenue"] + (["veto_unverified"] if hint != "none" else [])
            else:  # CTHRU lists every enacted item, so one missing from it was vetoed to $0
                used.add(key)
                amount, source, status = 0, "cthru", "vetoed"
        else:
            if covered:  # CTHRU has nothing for this fiscal year yet
                flags.append("cthru_mismatch")
            amount = final or ceiling
            if not final and ceiling:
                kind = "retained_revenue_ceiling"
                flags.append("retained_revenue")
            if hint != "none":
                flags.append("veto_unverified")
        if match and match["fund_numbers"] == CHARGEBACK_FUND and "isf_chargeback" not in flags:
            flags.append("isf_chargeback")
        if row["available_through"]:
            flags.append("multi_year")
        if item["confidence"] == "low" and "low_confidence_parse" not in flags:
            flags.append("low_confidence_parse")
        if not item["fund_splits_raw"] and match and match["fund_numbers"]:
            row["fund_numbers"] = match["fund_numbers"]
        row.update(
            section_type=section_type,
            funding_action="ORIG",
            amount_kind=kind,
            amount=amount,
            amount_source=source,
            veto_status=status,
            flags=";".join(dict.fromkeys(flags)),
        )
        out.append(row)
    return out


def annual_gaps(
    items: list[Mapping[str, str]],
    law_list: list[Mapping[str, str]],
    cthru: list[Mapping[str, str]],
    rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Problems (``combine_problems.csv``) for CTHRU money the annual rows can't carry: an account
    with enacted money in an in-scope GAA's fiscal year that has no item in that law's text read.
    Its money is missing from the totals until the reader finds the item, unless another row
    counts money for the account that year (1599-9817 in FY2022: CTHRU books it as original, but
    2021-102 §61 adds it). ``rows`` are the funding actions; the problem then names such a row
    and asks for the amounts to be compared, instead of saying the money is missing."""
    counted: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        if r["counts_toward_total"] == "true" and r["line_item"]:
            counted.setdefault((str(r["fiscal_year"]), r["line_item"]), []).append(r["record_id"])
    gaa_laws = {
        r["primary_fy"]: r["law_key"]
        for r in law_list
        if r["role"] == "in_scope" and r["law_type"] == "gaa" and r.get("primary_fy")
    }
    # §2D items count as read, though their rows come from federal_grant_rows
    read = {
        (_annual_fy(item, law), item["line_item"])
        for item, law in _gaa_items(items, law_list, with_skipped=True)
    }
    problems = []
    for r in cthru:
        amount = int(r["original_enacted"] or 0)
        key = (r["fiscal_year"], r["line_item"])
        if amount and r["fiscal_year"] in gaa_laws and key not in read:
            elsewhere = counted.get(key)
            if elsewhere:
                outcome = (
                    f"other rows count money for it that year (e.g. {elsewhere[0]}), so check "
                    "that the amounts agree"
                )
            else:
                outcome = "its money is not in the totals"
            problems.append(
                {
                    "record_id": "",
                    "law_key": gaa_laws[r["fiscal_year"]],
                    "section": "",
                    "line_item": r["line_item"],
                    "problem": (
                        f"CTHRU FY{r['fiscal_year']} has ${amount:,} for this account but no "
                        f"item was read from the law text: {outcome}"
                    ),
                }
            )
    return problems


def _law_type(laws: Mapping[str, Mapping[str, str]], item: Mapping[str, str]) -> str:
    return laws.get(item["law_key"], {}).get("law_type", "")


# -- Shared core (workstream A; DESIGN §5, §7.6–§7.8, §9.6, §10) ------------------------------
#
# Each piece of the work split (docs/Combine-Export-Work-Split.md) is one row builder: a function
# taking the loaded inputs (``load_inputs``) and the settings, and returning funding-action rows
# (§7.7) in source order. It may leave ``record_id`` and ``counts_toward_total`` empty: the core
# sets both. A row may also carry two extra keys for the fund splits, which aren't written:
# ``fund_splits_raw`` (items_raw's ``Fund name:percent;…``) and ``fund_numbers`` (CTHRU's
# ``;``-separated fund numbers). A row without either uses ``section_fund_default`` if it has one.

INPUTS = {
    "law_list": ("config", "law_list.csv"),
    "funds": ("config", "funds.csv"),
    "manual_rows": ("config", "manual_rows.csv"),
    "items_raw": ("interim", "items_raw.csv"),
    "bond_items_raw": ("interim", "bond_items_raw.csv"),
    "bond_authorizations_raw": ("interim", "bond_authorizations_raw.csv"),
    "amendments_raw": ("interim", "amendments_raw.csv"),
    "cthru_line_items": ("interim", "cthru_line_items.csv"),
}

# §10: what never counts toward the operating total, whatever the funding action's default.
NOT_COUNTED_SECTIONS = ("isf", "federal_grants", "trust_transfer", "interim")
NOT_COUNTED_KINDS = (
    "bond_authorization",
    "transfer",
    "interim",
    "prior_appropriation_continued",
    "none",
)
# fund_transfer_chain is a marker only (Q24): a move into a fund already doesn't count, by its
# amount_kind (transfer), and the move out of the fund into an item does
NOT_COUNTED_FLAGS = ("isf_chargeback", "trust_transfer")


# The stage that writes each interim input, for the message when one is missing (Q33)
INPUT_STAGES = {
    "items_raw": "read_items",
    "bond_items_raw": "read_bonds",
    "bond_authorizations_raw": "read_bonds",
    "amendments_raw": "read_amendments",
    "cthru_line_items": "cthru",
}


def missing_inputs(ctx: Context) -> list[str]:
    """The input files that don't exist yet (Q33): their rows would be silently missing."""
    dirs = {"config": ctx.config_dir, "interim": ctx.interim_dir}
    return [
        name for name, (where, filename) in INPUTS.items() if not (dirs[where] / filename).exists()
    ]


def load_inputs(ctx: Context) -> dict[str, list[dict[str, str]]]:
    """Every input table as rows; a file that doesn't exist yet gives no rows (see
    ``missing_inputs``, which ``run`` reports)."""
    dirs = {"config": ctx.config_dir, "interim": ctx.interim_dir}
    out = {}
    for name, (where, filename) in INPUTS.items():
        path = dirs[where] / filename
        out[name] = schemas.read_csv(path)[1] if path.exists() else []
    return out


def _bond_builder(inputs: Mapping[str, list], settings: Mapping[str, Any]) -> list[dict]:
    return bond_rows(
        inputs["bond_items_raw"],
        inputs["bond_authorizations_raw"],
        inputs["law_list"],
        settings["sources"]["session_law_url"],
    )


# One entry per piece of the work split; ``None`` until its owner adds the builder.
def _supplemental_builder(inputs: Mapping[str, list], settings: Mapping[str, Any]) -> list[dict]:
    return supplemental_rows(
        inputs["items_raw"],
        inputs["law_list"],
        inputs["cthru_line_items"],
        settings["sources"]["session_law_url"],
    )


def _amendment_builder(inputs: Mapping[str, list], settings: Mapping[str, Any]) -> list[dict]:
    items = starting_items(inputs)
    return amendment_rows(
        inputs["amendments_raw"],
        amendment_amounts(items, inputs["amendments_raw"], inputs["law_list"]),
        items,
        inputs["bond_authorizations_raw"],
        inputs["law_list"],
        settings["sources"]["session_law_url"],
        inputs["cthru_line_items"],
    )


def starting_items(inputs: Mapping[str, list]) -> list[dict[str, str]]:
    """Every item with a starting amount for the running amounts (§5.5): items_raw, bond_items_raw
    and hand-kept items in manual_rows (issue #41)."""
    return inputs["items_raw"] + inputs["bond_items_raw"] + manual_items(inputs["manual_rows"])


def _federal_grant_builder(inputs: Mapping[str, list], settings: Mapping[str, Any]) -> list[dict]:
    return federal_grant_rows(
        inputs["items_raw"], inputs["law_list"], settings["sources"]["session_law_url"]
    )


def _annual_builder(inputs: Mapping[str, list], settings: Mapping[str, Any]) -> list[dict]:
    return annual_rows(
        inputs["items_raw"],
        inputs["law_list"],
        inputs["cthru_line_items"],
        settings["sources"]["session_law_url"],
    )


BUILDERS = {
    "annual budget rows (E)": _annual_builder,
    "supplemental rows (B)": _supplemental_builder,
    "§2D federal grant rows (B)": _federal_grant_builder,
    "amendment rows (C)": _amendment_builder,
    "bond rows (A)": _bond_builder,
}


MANUAL_PIECE = "manual rows"  # the escape hatch's name among the pieces (run)


def manual_rows(rows: list[Mapping[str, str]]) -> list[dict[str, Any]]:
    """The escape hatch (§7.6) as funding-action rows: ``amount_source = manual``, flagged."""
    out = []
    for r in rows:
        row = {c: r.get(c, "") for c in schemas.columns("funding_actions")}
        row["amount_source"] = "manual"
        flags = [f for f in row["flags"].split(";") if f]
        if "manual_row" not in flags:
            flags.append("manual_row")
        row["flags"] = ";".join(flags)
        out.append(row)
    return out


def counts_toward_total(row: Mapping[str, Any]) -> bool:
    """Whether a row counts toward the operating total (§10). A partly federal row counts and the
    totals leave out its federal share; a wholly federal one doesn't count (Q1; Emma, 2026-11-10).
    """
    flags = str(row.get("flags") or "").split(";")
    if (
        row["section_type"] in NOT_COUNTED_SECTIONS
        or row["amount_kind"] in NOT_COUNTED_KINDS
        or any(f in flags for f in NOT_COUNTED_FLAGS)
        or float(row.get("federal_share") or 0) >= 1
    ):
        return False
    return schemas.FUNDING_ACTION_COUNTS_TOWARD_TOTAL[row["funding_action"]]


def operating_total(rows: list[Mapping[str, Any]]) -> int:
    """Net new appropriation authority (§10): counted rows, less their federal shares."""
    total = 0
    for r in rows:
        if str(r["counts_toward_total"]) == "true" and r["amount"] not in ("", None):
            total += round(int(r["amount"]) * (1 - float(r["federal_share"] or 0)))
    return total


def _fund_key(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip().lower()
    return re.sub(r"^the ", "", name)


def fund_splits(
    row: Mapping[str, Any], funds: list[Mapping[str, str]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """A row's fund splits (§5.6, §7.8) without ``record_id``, plus any problems.

    The law's printed split comes first, then CTHRU's fund numbers, then the fund named in the
    section preamble. CTHRU's numbers carry no shares, so several of them without a printed split
    give the funds with empty shares (Emma, 2026-11-10). A fund that isn't in ``config/funds.csv``
    is kept but reported, and not taken as federal.
    """
    by_name = {_fund_key(f["fund_name"]): f for f in funds}
    by_number = {f["fund_number"]: f for f in funds if f["fund_number"]}
    found: list[tuple[Mapping[str, str], str, float | str]] = []  # (funds.csv row, name, share)
    problems = []
    if row.get("fund_splits_raw"):
        for part in str(row["fund_splits_raw"]).split(";"):
            name, _, pct = part.rpartition(":")
            found.append((by_name.get(_fund_key(name), {}), name, float(pct) / 100))
    elif row.get("fund_numbers"):
        numbers = [n for n in str(row["fund_numbers"]).split(";") if n]
        share: float | str = 1.0 if len(numbers) == 1 else ""
        if len(numbers) > 1:
            problems.append(f"several CTHRU funds and no printed split: {';'.join(numbers)}")
        for n in numbers:
            found.append((by_number.get(n, {"fund_number": n}), n, share))
    elif row.get("section_fund_default"):
        name = str(row["section_fund_default"])
        found.append((by_name.get(_fund_key(name), {}), name, 1.0))
    out = []
    for fund, name, share in found:
        if "fund_name" not in fund:
            problems.append(f"fund not in config/funds.csv: {name}")
        out.append(
            {
                "fund_name": fund.get("fund_name", name),
                "fund_number": fund.get("fund_number", ""),
                "share": share,
                "is_federal": fund.get("is_federal", "false"),
            }
        )
    return out, problems


def _apply_splits(row: dict[str, Any], splits: list[Mapping[str, Any]]) -> None:
    """Main fund, federal share and federal flags from the splits (§5.6, §9.5). A row whose builder
    already set a federal share (bond rows, from their borrowing limit) keeps it."""
    known = [s for s in splits if s["share"] != ""]
    if known:
        row["fund_primary"] = max(known, key=lambda s: s["share"])["fund_name"]
    elif len(splits) == 1:
        row["fund_primary"] = splits[0]["fund_name"]
    if row.get("federal_share") not in ("", None) or not known:
        return
    share = sum(s["share"] for s in known if s["is_federal"] == "true")
    if not share:
        return
    row["federal_share"] = round(share, 6)
    flags = [f for f in str(row.get("flags") or "").split(";") if f]
    for f in ["federal"] + (["federal_mixed"] if share < 1 else []):
        if f not in flags:
            flags.append(f)
    row["flags"] = ";".join(flags)


def assign_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort rows by law, section and position in the law, then give each its Record ID (§9.6).
    The sort is stable, so rows at the same position keep their builders' order."""

    def order(r: Mapping[str, Any]) -> tuple:
        para = str(r.get("source_para_start") or "")
        return (
            _law_order(r["law_key"]),
            _section_order(r["section"]),
            int(para) if para.isdigit() else -1,
        )

    rows = sorted(rows, key=order)
    prefixes = []
    for r in rows:
        year, chapter = _law_order(r["law_key"])
        prefixes.append(
            schemas.record_id_prefix(
                year, chapter, r["section"], r["line_item"], r["funding_action"]
            )
        )
    for r, record_id in zip(rows, schemas.assign_record_ids(prefixes), strict=True):
        r["record_id"] = record_id
    return rows


def combine_rows(
    pieces: Mapping[str, list[dict[str, Any]]],
    law_list: list[Mapping[str, str]],
    funds: list[Mapping[str, str]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Every piece's rows as the funding actions table, with its fund splits and problems.

    Rows from laws that aren't ``in_scope`` are left out: reference-only laws are read only to
    look things up (§1). A manual row of a reference-only law is left out without a problem: it's
    there only to give an item its starting amount (1993-52 item 4000-8200, issue #41).
    Returns (funding actions, fund splits, problems), ready to write.
    """
    roles = {r["law_key"]: r["role"] for r in law_list}
    rows, problems = [], []
    for piece, piece_rows in pieces.items():
        for r in piece_rows:
            role = roles.get(r["law_key"])
            if role != "in_scope":
                if not (piece == MANUAL_PIECE and role == "reference_only"):
                    problems.append(_problem(r, f"{piece}: the law isn't in scope, row left out"))
                continue
            rows.append(dict(r))
    rows = assign_ids(rows)
    splits = []
    for r in rows:
        row_splits, row_problems = fund_splits(r, funds)
        _apply_splits(r, row_splits)
        r["counts_toward_total"] = "true" if counts_toward_total(r) else "false"
        splits += [{"record_id": r["record_id"], **s} for s in row_splits]
        problems += [_problem(r, p) for p in row_problems]
    columns = schemas.columns("funding_actions")
    return [{c: r.get(c, "") for c in columns} for r in rows], splits, problems


PROBLEM_COLUMNS = ("record_id", "law_key", "section", "line_item", "problem")


def _problem(row: Mapping[str, Any], problem: str) -> dict[str, Any]:
    return {c: row.get(c, "") for c in PROBLEM_COLUMNS[:-1]} | {"problem": problem}


# Funding actions an amount action (AMOUNT_ACTIONS) can become (§11.3, ``_change``)
AMOUNT_FUNDING_ACTIONS = ("INC", "RED", "NEW", "CAP", "PURP")


def running_amounts(
    rows: list[Mapping[str, Any]], amounts: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """``running_amounts.csv`` (§7.8): each amount from ``amendment_amounts`` (C), tied to the
    funding action that made it. Amendments with no funding-action row yet are left out.

    When one section changes an item more than once, each change has its own row (in source
    order, like the amounts), so each amount gets its own Record ID (Q33). Rows that don't change
    an amount (wording changes, date extensions, transfers) aren't events here."""
    by_key: dict[tuple, list[str]] = {}
    for r in rows:  # in Record ID order, which keeps each builder's source order
        if r["funding_action"] not in AMOUNT_FUNDING_ACTIONS:
            continue
        if r["funding_action"] == "PURP" and r["amount"] in ("", None):
            continue  # a wording change; a replaced item at the same amount is PURP $0
        key = (r["law_key"], r["section"], r["line_item"], r["target_law_key"])
        by_key.setdefault(key, []).append(r["record_id"])
    used: dict[tuple, int] = {}
    out = []
    for a in amounts:
        key = (a["law_key"], a["section"], a["target_item"], a["target_law_key"])
        ids = by_key.get(key, [])
        n = used.get(key, 0)
        used[key] = n + 1
        record_id = ids[n] if n < len(ids) else ""
        if record_id and a["amount_after"] not in ("", None):
            out.append(
                {
                    "target_law_key": a["target_law_key"],
                    "section": a["target_section"],
                    "line_item": a["target_item"],
                    "as_of_event": record_id,
                    "amount_after": a["amount_after"],
                }
            )
    return out


def _write(path: Path, columns: list[str] | tuple[str, ...], rows: list[Mapping]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(columns), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(ctx: Context) -> int:
    inputs = load_inputs(ctx)
    missing = missing_inputs(ctx)
    for name in missing:
        stage = INPUT_STAGES.get(name)
        hint = f" (run the {stage} stage first)" if stage else ""
        print(f"  WARNING: {INPUTS[name][1]} is missing{hint}: rows that need it are left out")
    pieces = {}
    for piece, builder in BUILDERS.items():
        if builder is None:
            print(f"  {piece}: not built yet")
            continue
        pieces[piece] = builder(inputs, ctx.settings)
        print(f"  {piece}: {len(pieces[piece])} rows")
    pieces["manual rows"] = manual_rows(inputs["manual_rows"])
    rows, splits, problems = combine_rows(pieces, inputs["law_list"], inputs["funds"])
    problems += [
        {
            "record_id": "",
            "law_key": "",
            "section": "",
            "line_item": "",
            "problem": f"input {INPUTS[name][1]} is missing: rows that need it are left out",
        }
        for name in missing
    ]
    problems += annual_gaps(
        inputs["items_raw"], inputs["law_list"], inputs["cthru_line_items"], rows
    )
    amounts = running_amounts(
        rows,
        amendment_amounts(starting_items(inputs), inputs["amendments_raw"], inputs["law_list"]),
    )
    bad = 0
    for table, table_rows in (
        ("funding_actions", rows),
        ("fund_splits", splits),
        ("running_amounts", amounts),
    ):
        path = ctx.interim_dir / f"{table}.csv"
        _write(path, schemas.columns(table), table_rows)
        bad += len(schemas.validate_file(table, path))
    _write(ctx.reports_dir / "combine_problems.csv", PROBLEM_COLUMNS, problems)
    print(
        f"  funding actions: {len(rows)} ({len(pieces['manual rows'])} manual); fund splits: "
        f"{len(splits)}; running amounts: {len(amounts)}; format problems: {bad}"
    )
    print(f"  problems: {len(problems)} (reports/combine_problems.csv)")
    print(f"  operating total: ${operating_total(rows):,}; capital total: ${capital_total(rows):,}")
    return 1 if bad else 0
