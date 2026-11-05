"""Stage 4 `read_bonds`: capital items in bond laws (incl. Chapter 90) to bond_items_raw.csv
(DESIGN §7.3, §11.2).

Owner: workstream A (Law list and bond bills). Bond laws print their items like budgets do (one
paragraph per item: ID, text, trailing amount, under ALL-CAPS secretariat and Title-case agency
headers), so this stage reads them with read_items' reader (B) and adds only what is specific to
bonds:
- **Pocket-vetoed items** (2020-383: "Governor pocket vetoed the following item", the item
  crossed out) never became law. They keep a row as a record, with ``amount`` blank, the printed
  amount in ``amount_struck`` and ``veto_kind_inline = disapproved``.
- Laws with ``parse_strategy = manual`` (text the API doesn't have, e.g. 1993-52) are skipped.

**Not yet: borrowing limits** ("issue and sell bonds … not exceeding $X") and check 7, pending
Q11/Q12. Unread paragraphs go to ``reports/unread_paragraphs_bonds.csv``.
"""

from __future__ import annotations

import json
import re

from ma_approps import read_items, schemas
from ma_approps.context import Context
from ma_approps.paragraphs import paragraphs

IMPLEMENTED = True
READER_VERSION = "0.1.0"

LAW_TYPES = ("bond",)
VETOED_ITEM_RE = re.compile(r"\bvetoed the following item\b", re.IGNORECASE)


def read_law(law_key: str, paras: list[dict]) -> tuple[list[dict], list[dict]]:
    """Items and unread paragraphs of one bond law, in source order."""
    items, unread = read_items.read_law(law_key, paras)
    for row in items:
        row["reader_version"] = READER_VERSION
        if VETOED_ITEM_RE.search(row["veto_annotation_raw"]):
            row["amount_struck"] = row["amount"] or row["amount_struck"]
            row["amount"] = ""
            row["veto_kind_inline"] = "disapproved"
            row["confidence"] = "high"
    return items, unread


def laws_to_read(ctx: Context) -> list[dict[str, str]]:
    _, rows = schemas.read_csv(ctx.config_dir / "law_list.csv")
    return [
        r
        for r in rows
        if r["law_type"] in LAW_TYPES
        and r["role"] != "excluded"
        and r["parse_strategy"] != "manual"
        and (ctx.law is None or r["law_key"] == ctx.law)
    ]


def run(ctx: Context) -> int:
    items: list[dict] = []
    unread: list[dict] = []
    missing = 0
    for law in laws_to_read(ctx):
        path = ctx.raw_dir / "sessionlaws" / law["acts_year"] / f"{law['chapter']}.json"
        if not path.exists():
            missing += 1
            continue
        html = json.loads(path.read_text("utf-8"))["ChapterText"]
        law_items, law_unread = read_law(law["law_key"], paragraphs(law["law_key"], html))
        items += law_items
        unread += law_unread
    read_items._write(
        ctx.interim_dir / "bond_items_raw.csv", schemas.columns("bond_items_raw"), items
    )
    read_items._write(
        ctx.reports_dir / "unread_paragraphs_bonds.csv", read_items.UNREAD_COLUMNS, unread
    )
    print(
        f"  bond items: {len(items)}; unread paragraphs: {len(unread)}; "
        f"laws not downloaded: {missing}"
    )
    return 0
