"""Stage 4 `read_bonds`: capital items and borrowing limits in bond laws (incl. Chapter 90) to
bond_items_raw.csv and bond_authorizations_raw.csv (DESIGN §7.3, §7.16, §11.2).

Owner: workstream A (Law list and bond bills). Bond laws print their items like budgets do (one
paragraph per item: ID, text, trailing amount, under ALL-CAPS secretariat and Title-case agency
headers), so this stage reads them with read_items' reader (B) and adds only what is specific to
bonds:
- **Pocket-vetoed items** (2020-383: "Governor pocket vetoed the following item", the item
  crossed out) never became law. They keep a row as a record, with ``amount`` blank, the printed
  amount in ``amount_struck`` and ``veto_kind_inline = disapproved``.
- **Borrowing limits** ("the state treasurer shall … issue and sell bonds … not exceeding, in the
  aggregate, $X"), one row each: what they cover (sections, or single items as in 2021-15 §6),
  the bond's name, term, final payable date and paying fund, how long §1 makes the money available,
  and the federal split (2026-11-06 decisions). Federal grant anticipation notes (2020-383 §34) are
  repaid from federal highway money but meet only "a portion of the expenditures", so their
  federal share is unknown.
- **Capital sections outside §2** (2023-2 §3–§3B, inside a supplemental budget; Q25): sections a
  borrowing limit covers that read_items doesn't read are read here with the same reader.
- Laws with ``parse_strategy = manual`` (text the API doesn't have, e.g. 1993-52) are skipped.

Unread paragraphs go to ``reports/unread_paragraphs_bonds.csv``. Comparing items with limits
(check 7) is validate's job.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from ma_approps import read_items, schemas
from ma_approps.context import Context
from ma_approps.paragraphs import key, paragraphs

IMPLEMENTED = True
READER_VERSION = "0.2.0"

LAW_TYPES = ("bond",)
VETOED_ITEM_RE = re.compile(r"\bvetoed the following item\b", re.IGNORECASE)

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = rf"{MONTH} \d{{1,2}}, \d{{4}}"
SECTION_RE = re.compile(r"^SECTION\s+(\d+[A-Z]{0,4})\b\.?", re.IGNORECASE)
BORROW_RE = re.compile(r"\bissue and sell (?:[\w-]+ ){0,4}?(?:bonds|notes)\b", re.IGNORECASE)
NOTES_RE = re.compile(r"\bfederal grant anticipation notes\b", re.IGNORECASE)
LIMIT_RE = re.compile(
    r"not exceeding,? in (?:the|an) aggregate(?: principal amount)?,?(?: of)? \$([\d,]+)",
    re.IGNORECASE,
)
COVERS_RE = re.compile(r"carry(?:ing)? out (.+?),? the (?:state )?treasurer", re.IGNORECASE)
RANGE_RE = re.compile(r"sections? (\d+[A-Z]*) to (\d+[A-Z]*)", re.IGNORECASE)
ITEM_RE = re.compile(r"\b(\d{4}-\d{4})\b")
# The name is quoted ("…Housing Act of 2023", which may contain commas) or not (…, and shall)
NAME_RE = re.compile(
    r"designated on their face,?\s*(?:[\"“]([^\"”]+)[\"”]|([^,]+?),? and shall)", re.IGNORECASE
)
TERM_RE = re.compile(r"maximum terms? of years,? not exceeding (\d+) years", re.IGNORECASE)
# Bonds: "payable not later than June 30, 2039"; notes: "final maturity … not later than …"
PAYABLE_BY_RE = re.compile(
    rf"(?:payable|final maturity of such notes[^.]*?shall be) not later than ({DATE})",
    re.IGNORECASE,
)
# "shall be payable from the General Fund or the Commonwealth Transportation Fund"; special
# obligation bonds name their fund the same way ("…from the Commonwealth Transportation Fund");
# grant anticipation notes are secured by "any pledge of federal highway construction funds"
PAYING_FUND_RE = re.compile(
    r"\bpayable (?:solely )?from the ((?:[A-Z][\w-]* )+?Fund(?: or the (?:[A-Z][\w-]* )+?Fund)?)"
    r"|\bpledge of (federal highway construction funds)"
)
# §1 says how long the money may be spent, for the whole act ("made available through
# December 31, 2030", 2024-139) or per section ("The sums set forth in sections 2 to 2B,
# inclusive, shall be made available until June 30, 2029", 2024-238)
AVAILABLE_RE = re.compile(
    rf"(?:sums set forth in (?P<sections>sections? [^.]*?),? )?(?:shall be )?made available "
    rf"(?:through|until) (?P<date>{DATE})",
    re.IGNORECASE,
)
# Items that may only be committed "based upon a prior or anticipated future commitment of
# federal funds": the borrowing limit is the state's share (§11.2 survey)
FEDERAL_ITEM_RE = re.compile(r"commitment of federal funds", re.IGNORECASE)
# Items whose borrowing depends on federal reimbursement, with no amount given (2021-15 4000-2026:
# "federal reimbursements received … shall be used to reduce the amount of bonds"; "bonds shall
# not be issued or sold for this item until federal reimbursement is secured"). Not the common
# "any federal reimbursement received … may be retained", which requires none (Emma, 2026-11-06).
FEDERAL_EXPECTED_RE = re.compile(
    r"federal reimbursements? received[^;]*?shall be used to reduce the amount of bonds"
    r"|bonds shall not be issued or sold[^;]*?until federal reimbursement",
    re.IGNORECASE,
)


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


def _sections(paras: list[dict]) -> list[tuple[str, list[dict]]]:
    """(section, paragraphs) in source order; paragraphs before SECTION 1 are dropped."""
    out: list[tuple[str, list[dict]]] = []
    for p in paras:
        m = SECTION_RE.match(key(p["text"]))
        if m:
            out.append((m.group(1).upper(), [p]))
        elif out:
            out[-1][1].append(p)
    return out


def _section_key(section: str) -> tuple[int, int, str]:
    m = re.match(r"(\d+)([A-Z]*)", section)
    return int(m.group(1)), len(m.group(2)), m.group(2)


def _iso(date: str) -> str:
    return datetime.strptime(date, "%B %d, %Y").date().isoformat()


def _covers(text: str, capital: list[str]) -> tuple[list[str], list[str]]:
    """(sections, items) a borrowing section pays for, e.g. "sections 2A to 2B, inclusive" or
    "item 4000-2026 of section 2". Only sections that hold items count."""
    m = COVERS_RE.search(text)
    if not m:
        return [], []
    span = m.group(1)
    items = ITEM_RE.findall(span)
    words = set(re.findall(r"\b(\d+[A-Z]{0,4})\b", ITEM_RE.sub(" ", span)))
    sections = {s for s in capital if s in words}
    if r := RANGE_RE.search(span):
        lo, hi = _section_key(r.group(1).upper()), _section_key(r.group(2).upper())
        sections |= {s for s in capital if lo <= _section_key(s) <= hi}
    return sorted(sections, key=_section_key), items


def _federal_split(text: str, authorized: int, total: int, covered: list[dict]) -> tuple[str, str]:
    """(federal_split, federal_share) under the 2026-11-06 decision (DESIGN §7.16): identified
    when a dollar figure follows from the law, unknown when federal money is expected but no
    amount is given."""
    if NOTES_RE.search(text):
        return "unknown", ""  # repaid from federal aid, but for "a portion" of the items (Emma)
    if total > authorized and any(FEDERAL_ITEM_RE.search(r["item_text"]) for r in covered):
        return "identified", str(total - authorized)
    if total > authorized or any(FEDERAL_EXPECTED_RE.search(r["item_text"]) for r in covered):
        return "unknown", ""
    return "none", ""


def _available(sections: list[tuple[str, list[dict]]], capital: list[str]) -> dict[str, str]:
    """Spending end date per capital section, from §1 ("" where §1 gives none)."""
    out = dict.fromkeys(capital, "")
    for name, paras in sections:
        if name != "1":
            continue
        for m in AVAILABLE_RE.finditer(" ".join(key(p["text"]) for p in paras)):
            named = m["sections"]
            covered = _covers(f"carry out {named}, the treasurer", capital)[0] if named else capital
            out.update(dict.fromkeys(covered, _iso(m["date"])))
    return out


def read_limits(
    law_key: str, sections: list[tuple[str, list[dict]]], items: list[dict]
) -> list[dict[str, str]]:
    """One bond_authorizations_raw row per borrowing section, in source order."""
    capital = sorted({r["section"] for r in items}, key=_section_key)
    available = _available(sections, capital)
    rows = []
    for name, paras in sections:
        text = " ".join(key(p["text"]) for p in paras)
        limit = LIMIT_RE.search(text)
        if not (BORROW_RE.search(paras[0]["text"]) and limit):
            continue
        covers, covered_items = _covers(text, capital)
        covered = [
            r
            for r in items
            if r["section"] in covers and (not covered_items or r["line_item"] in covered_items)
        ]
        authorized = int(limit.group(1).replace(",", ""))
        total = sum(int(r["amount"] or 0) for r in covered)
        split, share = _federal_split(text, authorized, total, covered)
        bond_name = NAME_RE.search(text)
        term = TERM_RE.search(text)
        payable_by = PAYABLE_BY_RE.search(text)
        name_found = (bond_name.group(1) or bond_name.group(2)).strip() if bond_name else ""
        fund = PAYING_FUND_RE.search(text)
        dates = {available[s] for s in covers}
        rows.append(
            {
                "law_key": law_key,
                "section": name,
                "covers_sections": ";".join(covers),
                "covers_items": ";".join(covered_items),
                "authorized": str(authorized),
                "items_total": str(total),
                "federal_share": share,
                "federal_split": split,
                "bond_name": name_found,
                "max_term_years": term.group(1) if term else "",
                "payable_by": _iso(payable_by.group(1)) if payable_by else "",
                "paying_fund": (fund.group(1) or fund.group(2)) if fund else "",
                "available_through": dates.pop() if len(dates) == 1 else "",
                "reader_version": READER_VERSION,
                "confidence": "high" if covers else "low",
            }
        )
    return rows


def _outside_capital(law_key: str, sections: list[tuple[str, list[dict]]]) -> list[dict]:
    """Items of capital sections numbered §3 and up (2023-2 §3–§3B, Q25).

    read_items stops at the first section above 2, so each such section is read on its own: its
    heading is renamed to a §2 heading for the reader ("SECTION 3A." -> "SECTION 2A.") and the
    rows get their real section back.
    """
    names = [n for n, _ in sections]
    borrowing = [
        " ".join(key(p["text"]) for p in paras)
        for _, paras in sections
        if BORROW_RE.search(paras[0]["text"])
    ]
    covered = {s for text in borrowing for s in _covers(text, [n for n in names if n != "1"])[0]}
    out = []
    for name, paras in sections:
        if name not in covered or re.match(r"^2[A-Z]*$", name):
            continue
        letters = re.match(r"\d+([A-Z]*)", name).group(1)
        renamed = SECTION_RE.sub(f"SECTION 2{letters}.", paras[0]["text"], count=1)
        head = dict(paras[0], text=renamed)
        rows, _ = read_law(law_key, [head, *paras[1:]])
        for r in rows:
            r["section"] = name
        out += rows
    return out


def laws_to_read(ctx: Context) -> list[dict[str, str]]:
    """Every law whose text is downloaded by the laws stage; bond laws are read in full, the
    others only for capital sections outside §2."""
    _, rows = schemas.read_csv(ctx.config_dir / "law_list.csv")
    return [
        r
        for r in rows
        if r["role"] != "excluded"
        and r["parse_strategy"] != "manual"
        and (ctx.law is None or r["law_key"] == ctx.law)
    ]


def run(ctx: Context) -> int:
    items: list[dict] = []
    limits: list[dict] = []
    unread: list[dict] = []
    missing = 0
    for law in laws_to_read(ctx):
        is_bond = law["law_type"] in LAW_TYPES
        path = ctx.raw_dir / "sessionlaws" / law["acts_year"] / f"{law['chapter']}.json"
        if not path.exists():
            missing += is_bond
            continue
        html = json.loads(path.read_text("utf-8"))["ChapterText"]
        paras = paragraphs(law["law_key"], html)
        sections = _sections(paras)
        law_items: list[dict] = []
        if is_bond:
            law_items, law_unread = read_law(law["law_key"], paras)
            unread += law_unread
        law_items += _outside_capital(law["law_key"], sections)
        if law_items:
            items += law_items
            limits += read_limits(law["law_key"], sections, law_items)
    read_items._write(
        ctx.interim_dir / "bond_items_raw.csv", schemas.columns("bond_items_raw"), items
    )
    read_items._write(
        ctx.interim_dir / "bond_authorizations_raw.csv",
        schemas.columns("bond_authorizations_raw"),
        limits,
    )
    read_items._write(
        ctx.reports_dir / "unread_paragraphs_bonds.csv", read_items.UNREAD_COLUMNS, unread
    )
    print(
        f"  bond items: {len(items)}; borrowing limits: {len(limits)}; "
        f"unread paragraphs: {len(unread)}; bond laws not downloaded: {missing}"
    )
    return 0
