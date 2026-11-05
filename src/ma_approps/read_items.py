"""Stage 3 `read_items`: line items in supplemental and annual budgets to items_raw.csv
(DESIGN §7.3, §11.2).

Owner: workstream B (Supplemental budgets). Supplementals: full items with amounts.
Annual budgets (GAAs): item text and printed amount only, used for Program / purpose and as the
printed side of the CTHRU comparison; GAA amounts in the dataset come from CTHRU.

The reader walks a law's paragraphs top to bottom (the §11.2 state machine):
- a **budget section** starts at a heading for section 2, 2A, 2B, 2CI, … and the first outside
  section (3 or higher) ends the budget part of the law;
- short paragraphs are **headers** (ALL CAPS = secretariat, otherwise agency);
- bold notes such as "Governor reduced the following item" are **veto notes** for the next item;
- an **item** starts with its ID and ends at the paragraph with the trailing amount;
- lines like "General Fund ...... 52.63%" are **fund splits** of the item above.

Anything else inside a section that has items goes to ``reports/unread_paragraphs.csv``.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ma_approps import schemas
from ma_approps.context import Context
from ma_approps.paragraphs import ITEM_START_RE, TRAILING_AMOUNT_RE, paragraphs

IMPLEMENTED = True
READER_VERSION = "0.1.0"

# Law types read here; bonds go to read_bonds (A) and interim budgets to read_amendments (C)
LAW_TYPES = ("gaa", "supplemental", "surplus", "other")

UNREAD_COLUMNS = ("law_key", "section", "para_idx", "text", "explanation")

# Section headings (Emma's issue #12): the standard "SECTION 2A." form, possibly followed by the
# preamble, or a paragraph that is only the heading, in any case and with or without a period
# ("Section 2" in 2021-24, "SECTION 2" in 2024-140). Roman-numeral parts may be printed with a
# period ("SECTION 2C.I." in 2021-76); the section is recorded without it ("2CI", as in 2023-77).
SECTION_RE = re.compile(r"^SECTION\s+(2[A-Z]{0,4}(?:\.[IVX]{1,4})?)\.(?:\s|$)")
SECTION_ALONE_RE = re.compile(r"^section\s+(2[a-z]{0,4}(?:\.[ivx]{1,4})?)\.?$", re.IGNORECASE)
# The first outside section ends the budget part, so quoted statutes ("Section 2PPP.") are ignored
OUTSIDE_RE = re.compile(r"^SECTION\s+(?:[3-9]|[1-9]\d+)[A-Z]{0,4}\.", re.IGNORECASE)
END_RE = re.compile(r"^Approved,")
# A replacement amount printed on its own line under a struck one (2025-9 item 1595-6368)
BARE_AMOUNT_RE = re.compile(r"^\$[\d,]+\.?$")

VETO_NOTE_RE = re.compile(r"^(?:The\s+)?(?:Governor|Legislature)\b", re.IGNORECASE)
# Veto notes are bold in most budgets, but not in 2021-24 and 2022-126
VETO_WORDS_RE = re.compile(r"following item|overr?ode|disapprov", re.IGNORECASE)
FUND_SPLIT_RE = re.compile(
    r"^[.\s]*(?P<fund>[A-Za-z][^$%]*?)\s*(?P<dots>\.{2,})?\s*(?P<pct>\d+(?:\.\d+)?)\s*(?P<sign>%?)$"
)
# A fund split printed on the same line as the amount ("... $1,233 Inland ... Fund ...... 100%")
SPLIT_TAIL_RE = re.compile(
    r"(?<=\d)\s+(?P<fund>[A-Z][^$%]*?)\s*\.{2,}\s*(?P<pct>\d+(?:\.\d+)?)\s*%$"
)
# An amount at the end with no dotted leader ("... wide area network $3,323,237"). This is the
# normal layout of the FY2021 and FY2022 budgets, so it doesn't lower confidence.
NO_LEADER_RE = re.compile(r"\s\$([\d,]+)\.?\s*$")
# Typos in printed amounts, accepted at medium confidence: a period as thousands separator
# ("$186.409,929"), a missing, doubled or spaced sign (". 3,369,875", ".$4,100,000",
# "$$515,000", "$ 2,629") and cents ("$4,371,777.42")
TYPO_AMOUNT_RE = re.compile(
    r"\.{2,}\s*(?:\$([\d,]+)\s+)?\.?\$?\$?\s*(\d{1,3}(?:[.,]\d{3})+)(?:\.\d{2})?\.?\s*$"
)
# The first fund named after "from the", up to 8 words ("General Fund", "Education and
# Transportation Fund", "federal COVID-19 response fund")
FUND_RE = re.compile(r"\bfrom the ((?:[\w'’&-]+\s+){1,8}?[Ff]und)\b")
FY_RE = re.compile(r"fiscal year (?:ending June 30, )?(\d{4})")
RR_CEILING_RE = re.compile(r"\bmay expend\b.{0,400}?\bnot more than \$([\d,]+)")
HEADER_MAX_LEN = 120  # "MASSACHUSETTS Commission on Lesbian, Gay, … Youth." is 92 characters
CAPS_HEADER_MAX_LEN = 150  # long ALL-CAPS office names (2024-140 "MASSACHUSETTS COMMISSION ON …")


@dataclass
class Item:
    section: str
    para_start: int
    line_item: str
    secretariat: str
    agency: str
    notes: list[str]
    paras: list[dict[str, Any]] = field(default_factory=list)
    splits: list[tuple[str, str]] = field(default_factory=list)
    complete: bool = False


def _money(s: str | None) -> str:
    return s.replace(",", "") if s else ""


def _section_of(text: str) -> str | None:
    m = SECTION_RE.match(text) or SECTION_ALONE_RE.match(text)
    return m.group(1).upper().replace(".", "") if m else None


def _preamble_facts(text: str) -> tuple[str, str]:
    """(fund, fiscal year) named in a section preamble, or blanks."""
    fund = FUND_RE.search(text)
    fy = FY_RE.search(text)
    return (fund.group(1) if fund else "", fy.group(1) if fy else "")


def _is_header(text: str) -> bool:
    limit = CAPS_HEADER_MAX_LEN if _is_caps(text) else HEADER_MAX_LEN
    return len(text) <= limit and "$" not in text and not ITEM_START_RE.match(text)


def _fund_split(text: str) -> tuple[str, str] | None:
    """(fund, percent) for a fund-split line such as "General Fund ...... 52.63%".

    Accepts the variants printed in the samples: no dotted leader ("Marijuana Regulation Fund
    100%"), a name not ending in "Fund" ("Local Capital Projects ..... 100%"), and a missing
    percent sign after a fund name ("General Fund ..... 80.32", 2024-140).
    """
    m = FUND_SPLIT_RE.match(text)
    if not m:
        return None
    fund = m["fund"].strip()
    named_fund = fund.endswith("Fund")
    if (m["sign"] and (m["dots"] or named_fund)) or (m["dots"] and named_fund):
        return fund, m["pct"]
    return None


def _ends_item(text: str) -> bool:
    text = SPLIT_TAIL_RE.sub("", text)
    return any(r.search(text) for r in (TRAILING_AMOUNT_RE, NO_LEADER_RE, TYPO_AMOUNT_RE))


def _is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _veto_kind(notes: list[str]) -> str:
    text = " ".join(notes).lower()
    if "overrode" in text or "overrid" in text:
        return "overridden"
    if "reduced" in text:
        return "reduced_and_wording" if "wording" in text else "reduced"
    if "disapproved" in text:
        return "disapproved"
    return "none"


def _drop_struck(text: str, struck: list[str]) -> tuple[str, bool]:
    """Remove struck runs from ``text`` in order (§11.2: final wording only).

    Returns False as the second value if a run couldn't be found.
    """
    ok, cursor = True, 0
    for run in struck:
        i = text.find(run, cursor)
        if i < 0:
            ok = False
            continue
        text = text[:i] + text[i + len(run) :]
        cursor = i
    return re.sub(r"\s+", " ", text).strip(), ok


def _row(law_key: str, item: Item, fund: str, fy: str) -> dict[str, str]:
    struck = [s for p in item.paras for s in p["struck"]]
    joined = " ".join(p["text"] for p in item.paras)
    splits = []
    while tail := SPLIT_TAIL_RE.search(joined):
        splits.insert(0, (tail["fund"].strip(), tail["pct"]))
        joined = joined[: tail.start()]
    amount = struck_amount = ""
    confidence = "high"
    first = None
    m = TRAILING_AMOUNT_RE.search(joined) if item.complete else None
    if m:
        first, last = m.group(1), m.group(2)
        amount = _money(last)
        if first:
            if f"${first}" in struck:
                struck_amount = _money(first)
            else:
                confidence = "medium"  # two trailing amounts, but the first isn't struck
        elif struck and struck[-1] == f"${last}":
            # the only amount is struck out: no final printed amount
            amount, struck_amount, confidence = "", _money(last), "medium"
            first = last
        joined = joined[: m.start()]
    elif item.complete and (m := TYPO_AMOUNT_RE.search(joined)):
        first = m.group(1)
        amount, confidence = re.sub(r"[.,]", "", m.group(2)), "medium"
        if first and f"${first}" in struck:
            struck_amount = _money(first)
        joined = joined[: m.start()]
    elif item.complete and (m := NO_LEADER_RE.search(joined)):
        amount = _money(m.group(1))
        joined = joined[: m.start()]
    text, ok = _drop_struck(joined, [s for s in struck if s != f"${first}"])
    if not ok:
        confidence = "medium"
    text = ITEM_START_RE.sub("", text, count=1).lstrip(" .")
    rr = RR_CEILING_RE.search(text)
    if not amount and not rr and not struck_amount:
        confidence = "low"  # no trailing amount and no retained-revenue ceiling
    return {
        "law_key": law_key,
        "section": item.section,
        "section_fund_default": fund,
        "fy_stated": fy,
        "para_start": str(item.para_start),
        "para_end": str(item.paras[-1]["para_idx"]),
        "line_item": item.line_item,
        "secretariat_header_raw": item.secretariat,
        "agency_header_raw": item.agency,
        "item_text": text,
        "amount": amount,
        "amount_struck": struck_amount,
        "retained_revenue_ceiling": _money(rr.group(1)) if rr else "",
        "fund_splits_raw": ";".join(f"{f}:{p}" for f, p in [*splits, *item.splits]),
        "veto_annotation_raw": " ".join(item.notes),
        "veto_kind_inline": _veto_kind(item.notes),
        "reader_version": READER_VERSION,
        "confidence": confidence,
    }


def read_law(law_key: str, paras: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Items and unread paragraphs of one law, in source order (DESIGN §11.2)."""
    items: list[dict[str, str]] = []
    unread: list[dict[str, str]] = []

    act_fund, act_fy = "", ""  # from section 1, for sections without their own preamble
    section: str | None = None
    fund = fy = ""
    secretariat = agency = ""
    notes: list[str] = []
    item: Item | None = None
    section_items: list[dict] = []
    section_unread: list[dict] = []
    in_preamble = False
    fund_prefix = ""  # first line of a fund name wrapped onto two lines

    def close_item() -> None:
        nonlocal item
        if item:
            section_items.append(_row(law_key, item, fund, fy))
            item = None

    def close_section() -> None:
        nonlocal section_items, section_unread
        close_item()
        items.extend(section_items)
        # A "section 2" with no items is policy text (e.g. 2021-35), not a budget section
        if section_items:
            unread.extend(section_unread)
        section_items, section_unread = [], []

    for n, p in enumerate(paras):
        text = p["text"]
        following = paras[n + 1]["text"] if n + 1 < len(paras) else ""
        if section is None and re.match(r"^SECTION\s+1\.", text):
            act_fund, act_fy = _preamble_facts(text)
        if OUTSIDE_RE.match(text) or END_RE.match(text):
            break
        name = _section_of(text)
        if name:
            if name != section:
                close_section()
                section, secretariat, agency, notes = name, "", "", []
                # Section 1 names the fund for the sections after it unless they name their own.
                # Not for 2C sections: they carry forward old balances, whatever their fund.
                fund, fy = ("", act_fy) if name.startswith("2C") else (act_fund, act_fy)
            own_fund, own_fy = _preamble_facts(text)
            fund, fy = own_fund or fund, own_fy or fy
            in_preamble = True
            continue
        if section is None:
            continue

        if item and not item.complete:
            if not (ITEM_START_RE.match(text) or VETO_NOTE_RE.match(text) or _is_caps(text)):
                item.paras.append(p)
                item.complete = _ends_item(text)
                continue
            close_item()

        if ITEM_START_RE.match(text):
            close_item()
            in_preamble = False
            item = Item(section, p["para_idx"], ITEM_START_RE.match(text).group(1),
                        secretariat, agency, notes, [p])
            item.complete = _ends_item(text)
            notes = []
        elif BARE_AMOUNT_RE.match(text) and item and not item.splits:
            item.paras.append(p)
        elif (split := _fund_split(text)) and item:
            item.splits.append((f"{fund_prefix} {split[0]}".strip(), split[1]))
            fund_prefix = ""
        elif item and _is_header(text) and _fund_split(following):
            # "Underground Storage Tank Petroleum" / "Product Cleanup Fund … 100%"
            fund_prefix = text
        elif VETO_NOTE_RE.match(text) and (p["bold"] or VETO_WORDS_RE.search(text)):
            close_item()
            notes.append(text)
        elif _is_header(text):
            close_item()
            in_preamble = False
            if _is_caps(text):
                secretariat, agency = text, ""
            else:
                agency = text
        elif in_preamble:
            own_fund, own_fy = _preamble_facts(text)
            fund, fy = own_fund or fund, own_fy or fy
        else:
            close_item()
            section_unread.append(
                {"law_key": law_key, "section": section, "para_idx": str(p["para_idx"]),
                 "text": text[:300], "explanation": ""}
            )
    close_section()
    return items, unread


def _write(path: Path, columns: tuple[str, ...] | list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def laws_to_read(ctx: Context) -> list[dict[str, str]]:
    _, rows = schemas.read_csv(ctx.config_dir / "law_list.csv")
    return [
        r
        for r in rows
        if r["law_type"] in LAW_TYPES
        and r["role"] != "excluded"
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
    _write(ctx.interim_dir / "items_raw.csv", schemas.columns("items_raw"), items)
    _write(ctx.reports_dir / "unread_paragraphs.csv", UNREAD_COLUMNS, unread)
    print(
        f"  items: {len(items)}; unread paragraphs: {len(unread)}; "
        f"laws not downloaded: {missing}"
    )
    return 0
