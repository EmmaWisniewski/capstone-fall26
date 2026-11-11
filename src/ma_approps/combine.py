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
- Any other GAA item in a section CTHRU covers (approp_main, surtax) with no CTHRU amount was
  vetoed to $0 (veto_status = vetoed); don't fall back to the printed amount. FY2025's law text
  doesn't mark its vetoes. Apply this only after the two cases above, never to §2D.
- CTHRU fund 0015 is §2B ISF chargebacks: counts_toward_total = false, even though CTHRU gives
  them non-zero fee-revenue caps ($632–704M a year).
"""

import csv
import re
from collections.abc import Mapping
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
    return [{c: r.get(c, "") for c in schemas.columns("funding_actions")} for r in out]


def capital_total(rows: list[Mapping[str, Any]]) -> int:
    """The capital total (New 1): bond amounts minus identified federal shares."""
    total = 0
    for r in rows:
        if r["funding_action"] != "CAP":
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

    - Each section's action comes from its preamble (``SUPPLEMENTAL_SECTIONS``). A §2 item that
      isn't in that fiscal year's GAA (read_items) or CTHRU is new money: ``NEW``, not ``INC``.
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
    funds = _cthru_funds(cthru)
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
        if action == "INC" and fy in budget_years and (fy, item["line_item"]) not in budgeted:
            action, kind = "NEW", "appropriation"  # not in that year's budget: a new item
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
NOT_COUNTED_FLAGS = ("isf_chargeback", "trust_transfer", "fund_transfer_chain")


def load_inputs(ctx: Context) -> dict[str, list[dict[str, str]]]:
    """Every input table as rows; a file that doesn't exist yet gives no rows."""
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


def _federal_grant_builder(
    inputs: Mapping[str, list], settings: Mapping[str, Any]
) -> list[dict]:
    return federal_grant_rows(
        inputs["items_raw"], inputs["law_list"], settings["sources"]["session_law_url"]
    )


BUILDERS = {
    "annual budget rows (E)": None,
    "supplemental rows (B)": _supplemental_builder,
    "§2D federal grant rows (B)": _federal_grant_builder,
    "amendment rows (C)": None,
    "bond rows (A)": _bond_builder,
}


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
    look things up (§1). Returns (funding actions, fund splits, problems), ready to write.
    """
    roles = {r["law_key"]: r["role"] for r in law_list}
    rows, problems = [], []
    for piece, piece_rows in pieces.items():
        for r in piece_rows:
            if roles.get(r["law_key"]) != "in_scope":
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


def running_amounts(
    rows: list[Mapping[str, Any]], amounts: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """``running_amounts.csv`` (§7.8): each amount from ``amendment_amounts`` (C), tied to the
    funding action that made it. Amendments with no funding-action row yet are left out."""
    by_key: dict[tuple, str] = {}
    for r in rows:
        key = (r["law_key"], r["section"], r["line_item"], r["target_law_key"])
        by_key.setdefault(key, r["record_id"])
    out = []
    for a in amounts:
        record_id = by_key.get((a["law_key"], a["section"], a["target_item"], a["target_law_key"]))
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
    pieces = {}
    for piece, builder in BUILDERS.items():
        if builder is None:
            print(f"  {piece}: not built yet")
            continue
        pieces[piece] = builder(inputs, ctx.settings)
        print(f"  {piece}: {len(pieces[piece])} rows")
    pieces["manual rows"] = manual_rows(inputs["manual_rows"])
    rows, splits, problems = combine_rows(pieces, inputs["law_list"], inputs["funds"])
    amounts = running_amounts(
        rows,
        amendment_amounts(
            inputs["items_raw"] + inputs["bond_items_raw"],
            inputs["amendments_raw"],
            inputs["law_list"],
        ),
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
