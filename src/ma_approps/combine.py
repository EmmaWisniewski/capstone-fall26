"""Stage 6 `combine`: build funding_actions.csv, fund_splits.csv, running_amounts.csv (DESIGN §5,
§7.6–§7.8).

Stub. Owner: everyone (Putting it together), coordinated by E. GAA rows come from
cthru_line_items.csv; everything else from items_raw, bond_items_raw, amendments_raw and the
manual_rows escape hatch. C owns the running-amounts logic; E owns the CTHRU comparison that sets
veto_status. Use schemas.record_id_prefix / assign_record_ids.
"""

import re

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
        before = amount.get(key)
        known = before is not None
        old, new = _int(a["old_figure"]), _int(a["new_figure"])
        check, note = "", ""
        if kind == "figure_change":
            if not known:
                check, after = "target_not_read", new
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


def run(ctx: Context) -> int:
    raise NotImplementedError
