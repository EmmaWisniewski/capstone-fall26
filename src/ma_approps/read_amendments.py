"""Stage 5 `read_amendments`: outside sections to data/interim/amendments_raw.csv (DESIGN §7.4,
§11.3).

Owner: workstream C (Amendments). Reads every cached law on the law list (hand-kept laws, with
`parse_strategy = manual`, have no cached text and are skipped) and, in each outside section (any
section other than the §2… appropriation sections, and the capital sections and borrowing limits
that read_bonds reads, such as 2023-2 §3–§3B), recognises the §11.3 patterns: figure changes,
date extensions, item insertions, replacements, strikes and renumberings, text-only changes,
transfers and direct appropriations. Interim ("1/12th") budgets are direct appropriations, so they
are read here rather than typed by hand. "Said item … of said section 2 of said chapter 28" is
resolved by carrying the last named law, section and item forward.

These go to reports/unread_sections.csv for a human to explain (§13.6): an outside section that
mentions dollars and an item or appropriation, or a transfer by the comptroller, but matches no
pattern; an amendment whose text names a line item but produces no row; and an outside section
that lists line items itself, which no stage reads. Only in-scope laws are reported: a
reference-only law is read for its items' history, but it adds no rows to the dataset, so its
unread sections are only counted. A row whose section has a misprinted dollar figure
("$15,000,0000") gets `low` confidence. A law misprinted in a citation is corrected through
config/citation_fixes.csv (§7.18).

A section the Governor returned with a recommendation of amendment isn't law in that chapter (the
Legislature's version, if any, is a later chapter), so it gives no rows and is listed in
reports/unread_sections.csv. An outside section that looks vetoed (struck-through text, or a
"Governor disapproved of the following section" note) is still read, but its rows get `low`
confidence and it is listed in reports/unread_sections.csv so a human checks whether the
Legislature overrode the veto. Inline veto markup is a hint, not truth (§11.4).

This stage only records what each law says. The running amounts table and the struck-figure check
(§5.5) need dates and CTHRU amounts, so they belong in `combine` and `validate`.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ma_approps import paragraphs, read_bonds, read_items, schemas
from ma_approps.context import Context

IMPLEMENTED = True
READER_VERSION = "0.11.0"

UNREAD_COLUMNS = ("law_key", "section", "reason", "text", "explanation")

# Sections 2, 2A … 2I of these law types hold line items, which read_items / read_bonds read.
APPROP_LAW_TYPES = ("gaa", "supplemental", "surplus", "bond")
APPROP_SECTION_RE = re.compile(r"^2[A-Z]*$")

ITEM = r"\d{4}-\d{4}"
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = rf"{MONTH} \d{{1,2}}, \d{{4}}"

SECTION_START_RE = re.compile(r"^SECTION\s+(\d+[A-Z]*)\b\.?\s*")
# A Section 2 heading printed alone, in any case and without a period: "Section 2" in the FY2022
# GAA (2021-24), "SECTION 2" in FY2025 (issue #12). Only when it is the whole paragraph, so a
# quoted "Section 67. Item …" inside an amendment is not taken for a new section.
SECTION2_HEADING_RE = re.compile(r"^section\s+(2[A-Z]{0,3})\.?$", re.I)
AMENDED_RE = re.compile(
    r"^(?P<subject>.{0,400}?)\s+(?:is|are)\s+hereby\s+(?:further\s+)?amended\b(?P<predicate>.*)$",
    re.S,
)
# ", as amended by section 229 of chapter 268 of the acts of 2022," names history, not the target
AS_AMENDED_RE = re.compile(
    r",\s*as (?:most recently |so |further )?(?:amended|appearing|inserted)\b[^,]*,"
)
# Chapter numbers can carry a half: "chapter 159A1⁄2 of the General Laws" (2020-383 §8). A
# chapter of the resolves isn't an appropriation act, so it is treated like the General Laws.
CHAPTER_RE = re.compile(
    r"\b(said\s+)?chapter\s+(\d+[A-Z]*(?:1⁄2|½|1/2)?)"
    r"(?:\s+of\s+the\s+acts\s+of\s+(\d{4})|\s+of\s+the\s+(General\s+Laws|resolves\s+of\s+\d{4}))?",
    re.I,
)
# Only the General Laws have an "Official Edition", and "as so appearing" refers back to one
# (2024-238 §101: "Section 29K of said chapter 29, as appearing in the 2022 Official Edition").
OFFICIAL_EDITION_RE = re.compile(r"Official Edition|as so appearing", re.I)
RENUMBER_RE = re.compile(
    rf'striking out the (?:figure|item number) "(?P<old>{ITEM})" and inserting in place'
    rf" thereof the following (?:figure|item number):-\s*(?P<new>{ITEM})"
)
ITEMS_RE = re.compile(rf"items?\s+({ITEM}(?:(?:,\s*|,?\s+and\s+){ITEM})*)")
# An amendment's subject that is an item, or a clause of one: "Clause (2) of item 3722-8899 of
# section 2 of chapter 494 of the acts of 1993" (2024-150 §61)
ITEM_SUBJECT_RE = re.compile(r"(?:clause\s+\([0-9a-z]+\)\s+of\s+)?(?:said\s+)?items?\b", re.I)

FIGURE_RE = re.compile(
    r'striking out(?P<line>, in lines? [\d ,to]+,)? the figure "\$\s*(?P<old>[\d,]+)"'
    r"(?P<where>[^\"]*?)\s*and inserting in place thereof(?P<each>, in each instance,)?"
    r" the following figure:-\s*\$\s*(?P<new>[\d,]+)"
)
YEAR_FIGURE_RE = re.compile(
    r'striking out the figure "(?P<old>\d{4})"[^"]*?and inserting in place thereof'
    r" the following figure:-\s*(?P<new>\d{4})\b"
)
DATE_WORDS_RE = re.compile(
    rf'striking out the words "[^"]*?(?P<old>{DATE})"[^"]*?and inserting in place thereof'
    rf" the following words:-[^.]*?(?P<new>{DATE})"
)
# 'striking out the words "July 1" … the following words:- November 30.' (2023-77 §49). The year
# is in the target item's own text, so both dates are recorded as written.
MONTH_DAY_RE = re.compile(
    rf'striking out the words "(?P<old>{MONTH} \d{{1,2}})"[^"]*?and inserting in place thereof'
    rf" the following words:-\s*(?P<new>{MONTH} \d{{1,2}})\s*\.?\s*$"
)
# "any unexpended balances, not exceeding a total of $40,000,000, in items 4000-0700 and 4000-1426
# of section 2 of chapter 126 of the acts of 2022 shall not revert … until September 1, 2023"
NOT_REVERT_RE = re.compile(
    rf"\bunexpended balances?\b[^.]*?\bin {ITEMS_RE.pattern}(?P<where>[^.]*?)"
    rf"\bshall not revert\b[^.]*?\buntil (?P<new>{DATE})"
)
AVAILABLE_UNTIL_RE = re.compile(
    rf"(?:inserting|adding)\b.*?the following words?:-.*?available\s+(?:until|through)\s+"
    rf"(?P<new>{DATE})"
)
DIRECT_RE = re.compile(
    r"(?:sum|amount) of \$\s*(?P<a>[\d,]+),?\s+(?:is|are) hereby appropriated"
    r"|(?:is|are) hereby appropriated,? (?:the (?:sum|amount) of )?\$\s*(?P<b>[\d,]+)"
)
TRANSFER_RE = re.compile(
    r"\btransfer\s+(?:up to |not more than |not less than )?(?:a total of )?"
    r"\$\s*(?P<amount>[\d,]+)\s+from\s+"
    r"(?P<tail>.*)"
)
# "the comptroller shall transfer from the General Fund to the Health Safety Net Trust Fund
# established in … the greater of $45,000,000 or 1/12 of …" (2023-28 §95)
TRANSFER_FROM_RE = re.compile(
    r"\btransfer\s+from\s+(?P<source>[^$]+?)\s+to\s+(?P<dest>[^$]{0,300}?),?\s+"
    r"(?P<qual>the greater of |the lesser of |up to |not more than |not less than )?"
    r"\$\s*(?P<amount>[\d,]+)"
)
# Other wordings of a transfer by the comptroller or the secretary of administration and finance
# (the actors of the `laws` stage's "transfers money" signal): a list, "transfer: (i) an amount not
# to exceed $10,000,000 from … to …; and (ii) …" (2021-102 §84) or "transferring no less than:
# (i) $350,000,000 to …" (2021-33 §2); no source, "transfer $1,399,699,283, or such amount as may
# be required, to …" (2022-126 §163); words between the figure and "from", "transfer
# $4,891,987,249.40 allocated to the commonwealth from …" (2021-22 §3, read as whole dollars).
TRANSFER_ACTOR_RE = re.compile(
    r"\b(?:comptroller|secretary of administration and finance)\b[^.;]{0,160}?"
    r"\b(?P<verb>transfer(?:s|red|ring)?)\b",
    re.I,
)
# The figure must come soon after the verb, as in the `laws` signal: not "reduce any transfers …
# by an amount not to exceed $375,000,000" (2024-140 §224) or "transfer funds in excess of …
# after the exhaustion of the $75,000,000" (2021-16 §11)
FIGURE_WINDOW = 60
TRANSFER_MONEY_RE = re.compile(
    TRANSFER_ACTOR_RE.pattern + rf"[^.;]{{0,{FIGURE_WINDOW}}}?\$\s*\d", re.I
)
# The clause ends at a semicolon, unless a list goes on ("; and (ii)"), or at a new sentence or
# subsection (". (b)")
TRANSFER_CLAUSE_END_RE = re.compile(r";(?!\s*(?:and|or)\s+\([ivx]+\))|(?<=\.)\s+(?=[A-Z(])")
LIST_ITEM_RE = re.compile(r"\((?:i{1,3}|iv|vi{0,3}|ix|x)\)\s*")
AMOUNT_RE = re.compile(r"\$\s*(?P<amount>\d[\d,]*)(?:\.\d\d)?")
# The figure isn't the amount moved: an estimate, or a figure for each of several years
# (2025-73 §191: "$50,000,000 each such fiscal year")
ESTIMATE_RE = re.compile(r",?\s*(?:or such (?:other )?amount|each\b)")
FUND_RE = re.compile(r"\bfrom the ((?:[A-Z][\w’'&.-]*\s+)+?Fund)\b")
# A fund named in a transfer, even in lowercase: "the federal COVID-19 response fund"; "and" only
# inside a capitalised name ("the Disaster Relief and Resiliency Fund", 2024-140 §229). Not "the
# undesignated fund balance in the General Fund" (2022-268 §265): that money is the General Fund's.
FUND_NAME_RE = re.compile(
    r"\bthe ((?:(?:(?!(?:the|of|in|or|and|to|from|by|for|established|section|chapter|item)\b)"
    r"[\w’'&.-]+|and(?= [A-Z])) ){0,8}?[Ff]und)\b(?!\s+balance)"
)
MONEY_RE = re.compile(r"\$\s*\d")
ITEM_OR_APPROP_RE = re.compile(rf"\bitems?\s+{ITEM}|appropriat", re.I)
# A dollar figure whose commas aren't in groups of three is a misprint, in this law or in the one
# it quotes: 2022-42 §46 strikes "$15,000,0000" from 2021 ch. 102, which isn't $150,000,000
DOLLAR_FIGURE_RE = re.compile(r"\$\s*(\d[\d,]*\d|\d)")
WELL_FORMED_FIGURE_RE = re.compile(r"\d{1,3}(?:,\d{3})*|\d+")
# A paragraph that starts with a line item number ("7002-8041.. For …"): an outside section that
# lists items itself, like the capital sections 3 to 3B of 2023 ch. 2
ITEM_LINE_RE = re.compile(rf"{ITEM}(?!\d)")
# Printed just before what it is about: "The Governor disapproved of the following section, …",
# "Governor returned the following section with recommendation of amendment, …"
GOVERNOR_NOTE_RE = re.compile(r"^(?:The )?Governor (?:disapproved|returned)\b")


def _sections(paras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group paragraphs into sections, in source order: ``section``, ``texts`` and ``vetoed``.

    A Governor's note comes just before what it is about, so it is held back: before a new
    section it only marks that section, and anywhere else it stays in place in the text. A section
    is ``vetoed`` if any of its text is struck through or a note says the Governor disapproved,
    and ``returned`` if a note says the Governor returned it with a recommendation of amendment.
    """
    out: list[dict[str, Any]] = []
    notes: list[str] = []
    for p in paras:
        if GOVERNOR_NOTE_RE.match(p["text"]):
            notes.append(p["text"])
            continue
        if m := SECTION_START_RE.match(p["text"]) or SECTION2_HEADING_RE.match(p["text"]):
            returned = any("returned" in n and "amendment" in n for n in notes)
            out.append(
                {"section": m[1].upper(), "texts": [], "vetoed": False, "returned": returned}
            )
        elif out:
            out[-1]["texts"] += notes
        if out:
            out[-1]["texts"].append(p["text"])
            disapproved = any("disapproved" in n for n in notes)
            out[-1]["vetoed"] |= bool(p["struck"]) or disapproved
        notes = []
    return out


def _int(figure: str) -> int:
    return int(figure.replace(",", ""))


def _misprinted_figure(text: str) -> bool:
    """True if any dollar figure in ``text`` has commas out of place ("$15,000,0000")."""
    return any(not WELL_FORMED_FIGURE_RE.fullmatch(f) for f in DOLLAR_FIGURE_RE.findall(text))


def _iso(day: str) -> str:
    return datetime.strptime(day, "%B %d, %Y").date().isoformat()


def _chapter_law(m: re.Match, chapters: dict[str, str]) -> str | None:
    """Law key for a chapter mention; "GL" for the General Laws; None if unknown."""
    if m[3]:
        return schemas.law_key(m[3], m[2])
    if m[1]:
        return chapters.get(m[2])
    return "GL"  # "of the General Laws", a resolve, or a bare "chapter 40R"


def _remember_chapters(text: str, chapters: dict[str, str]) -> None:
    """Record every chapter mention so a later "said chapter N" can be resolved."""
    for m in CHAPTER_RE.finditer(text):
        if not m[1]:
            chapters[m[2]] = _chapter_law(m, chapters)


def _resolve(
    subject: str, law_key: str, chapters: dict[str, str], last: dict[str, Any]
) -> tuple[str, str | None, list[str]] | None:
    """(target law key, target section, items) named by an amendment's subject, or None."""
    items = re.findall(ITEM, subject) if ITEM_SUBJECT_RE.match(subject) else []
    sec = re.search(r"\bsection\s+(\d+[A-Z]*)\b", subject, re.I)
    ch = CHAPTER_RE.search(subject)
    if "of this act" in subject:
        law = law_key
    elif ch:
        law = _chapter_law(ch, chapters)
    elif "General Laws" in subject:  # "The General Laws are hereby amended by inserting …"
        law = "GL"
    elif "said" in subject.lower():
        law = last["law"]
    else:
        law = None
    if law is None:
        return None
    section = sec[1] if sec else (last["section"] if law == last["law"] else None)
    if items and law != "GL" and section is None:
        return None
    return law, section, items


def _inserted_items(paras: list[str]) -> dict[str, int | None]:
    """Items printed after an "inserting … the following item:-" clause, with trailing amounts."""
    items: dict[str, int | None] = {}
    current = None
    for text in paras:
        # No space is required after the ID ("4125-0122vFor" in 2024-140); the same rule as
        # paragraphs.ITEM_START_RE on Tierney's read_items branch (PR #15)
        m = re.match(rf"({ITEM})(?!\d)", text)
        if m:
            current = m[1]
            items[current] = None
        if current and items[current] is None:
            a = re.search(r"\$\s*([\d,]+)\.?\s*$", text)
            if a:
                items[current] = _int(a[1])
    return items


def _amendment_actions(
    predicate: str, items: list[str], rest: list[str]
) -> list[dict[str, Any]] | None:
    """Actions for one "is hereby amended …" clause. [] if it isn't about items; None if an item
    amendment matched no pattern."""
    m = re.search(rf"striking out {ITEMS_RE.pattern}", predicate)
    if m:
        struck = re.findall(ITEM, m[1])
        if "inserting in place thereof the following item" in predicate:
            new = _inserted_items(rest)
            if not new:  # the new item couldn't be found
                return [
                    {"action_type": "item_replace", "target_item": i, "confidence": "low"}
                    for i in struck
                ]
            # The same number is a replacement. A different number (2022-268 §228 replaces
            # 4003-0100 with 4003-0122) strikes the old item and inserts the new one.
            actions = [
                {
                    "action_type": "item_replace",
                    "target_item": i,
                    "new_figure": new[i],
                    "confidence": "high" if new[i] is not None else "low",
                }
                if i in new
                else {"action_type": "item_strike", "target_item": i}
                for i in struck
            ]
            return actions + [
                {
                    "action_type": "item_insert",
                    "target_item": i,
                    "new_figure": amount,
                    "confidence": "high" if amount is not None else "low",
                }
                for i, amount in new.items()
                if i not in struck
            ]
        return [{"action_type": "item_strike", "target_item": i} for i in struck]
    if re.search(
        rf"inserting (?:after|before) item {ITEM},? the following items?:-"
        r"|adding the following items?:-",
        predicate,
    ):
        return [
            {"action_type": "item_insert", "target_item": i, "new_figure": amount}
            for i, amount in _inserted_items(rest).items()
        ]
    # An item renumbered in an earlier law (2021-102 §46: 'striking out the figure "7002-0015"
    # and inserting in place thereof the following figure:- 7002-0016'): no money changes
    if m := RENUMBER_RE.search(predicate):
        return [{"action_type": "purpose_change", "target_item": m["old"], "to_item": m["new"]}]
    if not items:
        return []

    action: dict[str, Any]
    if m := FIGURE_RE.search(predicate):
        # "Both times it appears … in each instance" is usually a retained-revenue item, whose
        # spending ceiling and amount are the same figure (2023-77 §81, Q21). "In line 7" or
        # "the second time it appears" may be an earmark in the text, so it stays low;
        # combine's struck-figure check confirms either way.
        where = m["where"].strip(" ,")
        everywhere = re.fullmatch(r"(?:both times|each time) it appears", where)
        partial = m["line"] or (where and not everywhere)
        action = {
            "action_type": "figure_change",
            "old_figure": _int(m["old"]),
            "new_figure": _int(m["new"]),
            "confidence": "low" if partial else "high",
        }
    elif m := YEAR_FIGURE_RE.search(predicate):
        action = {"action_type": "date_extend", "old_date": m["old"], "new_date": m["new"]}
    elif m := DATE_WORDS_RE.search(predicate):
        action = {
            "action_type": "date_extend",
            "old_date": _iso(m["old"]),
            "new_date": _iso(m["new"]),
        }
    elif m := MONTH_DAY_RE.search(predicate):
        # no year in the law's words; it is in the target item's text
        action = {
            "action_type": "date_extend",
            "old_date": m["old"],
            "new_date": m["new"],
            "confidence": "medium",
        }
    elif m := AVAILABLE_UNTIL_RE.search(predicate):
        action = {"action_type": "date_extend", "new_date": _iso(m["new"])}
    # "inserting place thereof", without "in", is the law's own slip (2024-150 §104, §112)
    elif re.search(r"\bstriking out\b.*\binserting (?:in )?place thereof\b", predicate):
        action = {"action_type": "purpose_change"}
    elif re.search(r"\b(?:inserting|adding)\b", predicate):
        action = {"action_type": "text_insert"}
    elif re.search(r"\bstriking out\b", predicate):
        action = {"action_type": "text_strike"}
    else:
        return None
    return [{**action, "target_item": i} for i in items]


def _sentence_actions(
    law_key: str, section: str, full: str, chapters: dict[str, str]
) -> list[dict[str, Any]]:
    """Direct appropriations, transfers and non-reversions in a section that does not amend
    another law."""
    actions = []
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z])", full):
        for m in NOT_REVERT_RE.finditer(sentence):
            ch = CHAPTER_RE.search(m["where"])
            law = _chapter_law(ch, chapters) if ch else law_key
            sec = re.search(r"\bsection\s+(\d+[A-Z]*)\b", m["where"])
            if law is None or law == "GL":
                continue
            actions += [
                {
                    "action_type": "date_extend",
                    "target_law_key": law,
                    "target_section": sec[1] if sec else None,
                    "target_item": i,
                    "new_date": _iso(m["new"]),
                    # often only part of the balance ("not exceeding a total of $40,000,000")
                    "confidence": "medium",
                }
                for i in re.findall(ITEM, m[1])
            ]
        item = re.search(rf"\bitem\s+({ITEM})", sentence)
        fund = FUND_RE.search(sentence)
        for m in DIRECT_RE.finditer(sentence):
            actions.append(
                {
                    "action_type": "direct_appropriation",
                    "target_law_key": law_key,
                    "target_section": section,
                    "target_item": item[1] if item else None,
                    "amount": _int(m["a"] or m["b"]),
                    "fund_raw": fund[1] if fund else None,
                }
            )
        transfers, read = [], []
        for m in TRANSFER_RE.finditer(sentence):
            transfers.append(_transfer(m["amount"], *_source_and_destination(m["tail"])))
            read.append(m.span())
        for m in TRANSFER_FROM_RE.finditer(sentence):
            # "the greater of $45,000,000 or 1/12 of …": the stated figure is only a bound
            bound = m["qual"] in ("the greater of ", "the lesser of ")
            transfers.append(_transfer(m["amount"], m["source"], m["dest"], bound))
            read.append(m.span())
        transfers += _other_transfers(sentence, read)
        actions += _one_per_transfer(transfers)
    return actions


def _one_per_transfer(transfers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same figure twice in a sentence, with no different destinations, is one transfer with
    a fallback source: "transfer $75,000,000 to the COVID-19 … Fund … from amongst federal funds
    …; provided, however, that if … no such funds are available, … transfer $75,000,000 from other
    funding sources, including the General Fund" (2021-16 §13). It becomes one `low` row with both
    rows' items and funds, so nobody reads $150,000,000 (Emma's review of PR #39). Separate
    transfers of the same figure to different funds (2021-102 §84) stay separate."""
    out: list[dict[str, Any]] = []
    for t in transfers:
        dest = (t["to_item"], t["to_fund"])
        same = next(
            (
                o
                for o in out
                if o["amount"] == t["amount"]
                and (
                    (o["to_item"], o["to_fund"]) == dest
                    or not any(dest)
                    or not o["to_item"]
                    and not o["to_fund"]
                )
            ),
            None,
        )
        if same is None:
            out.append(t)
            continue
        for k in ("from_item", "to_item", "to_fund"):
            same[k] = same[k] or t[k]
        funds = [f for r in (same, t) for f in (r["fund_raw"] or "").split("; ") if f]
        same["fund_raw"] = "; ".join(dict.fromkeys(funds)) or None
        same["confidence"] = "low"
    return out


def _source_and_destination(tail: str) -> tuple[str, str]:
    """Split the words after "from" into a transfer's source and destination.

    The source runs to the first "to" (or "into") after its first fund or item: "the prescription
    advantage program in line-item 9110-1455 … and the Health Safety Net Trust Fund … to support".
    A "to" before that is part of its description ("the startup costs for Revolution 250 related
    to the planning … established in item 1599-6077 … to the Massachusetts Tourism Trust Fund",
    2023-2 §76). The destination is the first item after the split, however it is named: "to item
    …" or "to the reserve established in item 1599-0514 of section 2A of chapter 77 …"
    (2024-88 §25).
    """
    anchor = re.search(rf"{ITEM}|\b[Ff]und\b", tail)
    to = re.compile(r"\b(?:in)?to\b")
    cut = to.search(tail, anchor.end() if anchor else 0)
    if not cut and anchor:
        # the first fund or item named is the destination: "from income surtax revenue, as defined
        # by … , to the Student Opportunity Act Investment Fund" (2025-73 §177)
        cut = next(reversed(list(to.finditer(tail, 0, anchor.start()))), None)
    return (tail[: cut.start()], tail[cut.end() :]) if cut else (tail, "")


def _funds(text: str) -> str | None:
    return "; ".join(dict.fromkeys(FUND_NAME_RE.findall(text))) or None


def _transfer(amount: str, source: str, dest: str, low: bool = False) -> dict[str, Any]:
    from_item = re.search(rf"\bitems?\s+({ITEM})", source)
    to_item = re.search(rf"\bitems?\s+({ITEM})", dest)
    # The funds the money goes to are those named before any item, purpose or proviso: not "the
    # reserve established in item 1599-0514 … for the purposes of …" (2024-88 §25), but both of
    # "the Transitional Escrow Fund … or the federal COVID-19 response fund" (2024-206 §58)
    head = re.split(rf"{ITEM}|\bfor (?:the )?purposes?\b|;|\bprovided\b", dest, maxsplit=1)[0]
    return {
        "action_type": "transfer",
        "amount": _int(amount),
        "from_item": from_item[1] if from_item else None,
        "to_item": to_item[1] if to_item else None,
        "fund_raw": _funds(source),
        "to_fund": _funds(head),
        # fund-to-fund transfers carry no items; a human should confirm them
        "confidence": "low" if low else ("high" if from_item and to_item else "medium"),
    }


def _other_transfers(sentence: str, read: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Transfers by the comptroller or the secretary of administration and finance in the other
    wordings (TRANSFER_ACTOR_RE): one per figure, or per "(i)", "(ii)" … in a list. ``read`` are
    the spans the two transfer patterns already read."""
    actions: list[dict[str, Any]] = []
    end = 0
    for m in TRANSFER_ACTOR_RE.finditer(sentence):
        if m.start() < end or any(a <= m.start("verb") < b for a, b in read):
            continue  # "said transfers" inside a clause already read
        rest = sentence[m.end() :]
        stop = TRANSFER_CLAUSE_END_RE.search(rest)
        clause = rest[: stop.start()] if stop else rest
        end = m.end() + len(clause)
        parts = LIST_ITEM_RE.split(clause)[1:] if re.search(r":\s*\(i\)", clause) else [clause]
        for part in parts:
            figure = AMOUNT_RE.search(part)
            if not figure or figure.start() > FIGURE_WINDOW:
                continue
            after = part[figure.end() :]
            source = re.search(r"\bfrom\s+", after)
            if source:
                source_text, dest = _source_and_destination(after[source.end() :])
                # the destination first: "transfer $310,000,000 to the General Fund from the
                # Commonwealth Stabilization Fund" (2008-182 §82), but not "$4,891,987,249.40
                # allocated to the commonwealth from …" (2021-22 §3)
                to = re.search(r"\b(?:in)?to\b", after[: source.start()])
                first = after[to.end() : source.start()] if to else ""
                if FUND_NAME_RE.search(first) or re.search(ITEM, first):
                    dest = first
            else:  # "transfer $20,000,000 to the …", "… of the General Fund to the …"
                cut = re.search(r"\b(?:in)?to\b", after)
                source_text, dest = (after[: cut.start()], after[cut.end() :]) if cut else ("", "")
            actions.append(
                _transfer(figure["amount"], source_text, dest, bool(ESTIMATE_RE.match(after)))
            )
    return actions


def read_law(
    law_key: str, law_type: str, html: str, fixes: dict[tuple[str, str], str] | None = None
) -> tuple[list[dict], list[dict]]:
    """amendments_raw rows and unread_sections rows for one law, in source order.

    ``fixes`` maps (section, law cited) to the law meant, for citations misprinted in this law
    (config/citation_fixes.csv, e.g. ("35", "2022-24") -> "2021-24" in 2024-248).
    """
    fixes = fixes or {}
    rows: list[dict] = []
    unread: list[dict] = []
    chapters: dict[str, str] = {}
    last: dict[str, Any] = {"law": None, "section": None}
    paras = paragraphs.paragraphs(law_key, html)
    capital = read_bonds.capital_sections(paras)  # read_bonds reads these sections' items
    # ... and, in laws with capital items, the borrowing limits ("issue and sell bonds", §7.16)
    borrows = law_type in read_bonds.LAW_TYPES or bool(capital)
    for s in _sections(paras):
        section, texts = s["section"], s["texts"]
        keyed = [paragraphs.key(t) for t in texts]
        full = "\n".join(keyed)
        if (
            (law_type in APPROP_LAW_TYPES and APPROP_SECTION_RE.match(section))
            or section in capital
            or (borrows and read_bonds.BORROW_RE.search(texts[0]))
        ):
            _remember_chapters(full, chapters)
            continue

        actions: list[dict[str, Any]] = []
        reason = None
        target = None
        body = SECTION_START_RE.sub("", keyed[0], count=1)
        m = None if body.startswith("Notwithstanding") else AMENDED_RE.match(body)
        rest, nested = keyed[1:], False
        # An amendment of an amendment (2023-77 §56): "Said chapter 102 is hereby further amended
        # by striking out section 67 … and inserting in place thereof the following section:-
        # Section 67. Item 8200-0200 of said section 2 of said chapter 24 is hereby amended …".
        # Read the inner amendment; its "said" references belong to the earlier law, so a human
        # confirms the result.
        if m and rest and re.search(r"the following section:-\s*$", m["predicate"]):
            inner = re.match(r"Section\s+\d+[A-Z]*\.\s*(.*)$", rest[0], re.S)
            if inner and (inner_m := AMENDED_RE.match(inner[1])):
                m, rest, nested = inner_m, rest[1:], True
        if m:
            target = _resolve(AS_AMENDED_RE.sub("", m["subject"]), law_key, chapters, last)
            if target is None and OFFICIAL_EDITION_RE.search(m["subject"]):
                target = ("GL", None, [])
            if target is None:
                reason = "could not tell which law this section amends"
            elif target[0] != "GL":
                predicate = AS_AMENDED_RE.sub("", m["predicate"])
                found = _amendment_actions(predicate, target[2], rest)
                if found is None:
                    reason = "changes a line item in a way no pattern recognises"
                else:
                    actions = [
                        {
                            "target_law_key": target[0],
                            "target_section": target[1],
                            **a,
                            **({"confidence": "low"} if nested else {}),
                        }
                        for a in found
                    ]
                if not nested:
                    last = {"law": target[0], "section": target[1]}
        else:
            actions = _sentence_actions(law_key, section, full, chapters)

        general_laws = target is not None and target[0] == "GL"
        # read_items reads the §2… sections of these law types, so their item lists are covered
        covered = law_type in read_items.LAW_TYPES and APPROP_SECTION_RE.match(section)
        if not m and not reason and not covered and any(ITEM_LINE_RE.match(t) for t in keyed[1:]):
            reason = "lists line items itself, which no stage reads"
        if not actions and not reason and not general_laws:
            if m and re.search(ITEM, full):
                # 2024-150 §61 rewrites a proviso in "Clause (2) of item 3722-8899" (no dollars)
                reason = "amends text that names a line item but matched no pattern"
            elif MONEY_RE.search(full) and ITEM_OR_APPROP_RE.search(full):
                reason = "mentions dollars and an item or appropriation but matched no pattern"
            elif TRANSFER_MONEY_RE.search(full):
                # a transfer between funds names no item: 2021-22 §3 was missed this way
                reason = "mentions dollars and a transfer by the comptroller but matched no pattern"
        if actions and s["vetoed"]:
            reason = "looks vetoed (struck text or a veto note); check whether it was overridden"
        if s["returned"] and (actions or reason):
            # Not law in this chapter: the Legislature acts on the Governor's amendment in a
            # separate bill, which becomes its own chapter (2021-24 §102–§103 became 2021 ch. 33).
            # Listed only when it would have given rows or been unread anyway.
            actions = []
            reason = (
                "returned by the Governor with a recommendation of amendment, so it isn't law in"
                " this chapter; the Legislature's version, if any, is a later chapter"
            )
        if reason:
            unread.append(
                {"law_key": law_key, "section": section, "reason": reason, "text": texts[0][:500]}
            )
        low = s["vetoed"] or _misprinted_figure(full)
        for a in actions:
            fixed = fixes.get((section, a.get("target_law_key") or ""))
            rows.append(
                {
                    "law_key": law_key,
                    "section": section,
                    "source_text": "\n".join(texts),
                    "reader_version": READER_VERSION,
                    "confidence": "high",
                    **a,
                    # a corrected citation: the law named isn't the one meant (§7.18)
                    **({"target_law_key": fixed, "confidence": "medium"} if fixed else {}),
                    **({"confidence": "low"} if low else {}),
                }
            )
        _remember_chapters(full, chapters)
    return rows, unread


def _write(path: Path, columns: list[str] | tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: "" if r.get(c) is None else r[c] for c in columns})


def citation_fixes(ctx: Context) -> dict[str, dict[tuple[str, str], str]]:
    """config/citation_fixes.csv as {law_key: {(section, printed): target_law_key}} (§7.18)."""
    path = ctx.config_dir / "citation_fixes.csv"
    fixes: dict[str, dict[tuple[str, str], str]] = {}
    if path.exists():
        for r in schemas.read_csv(path)[1]:
            fixes.setdefault(r["law_key"], {})[r["section"], r["printed"]] = r["target_law_key"]
    return fixes


def run(ctx: Context) -> int:
    all_fixes = citation_fixes(ctx)
    _, laws = schemas.read_csv(ctx.config_dir / "law_list.csv")
    laws = [
        r
        for r in laws
        if r["role"] in ("in_scope", "reference_only") and r["parse_strategy"] != "manual"
    ]
    if ctx.law:
        laws = [r for r in laws if r["law_key"] == ctx.law]
    rows: list[dict] = []
    unread: list[dict] = []
    read, missing, reference_unread = 0, 0, 0
    for law in sorted(laws, key=lambda r: (int(r["acts_year"]), int(r["chapter"]))):
        path = ctx.raw_dir / "sessionlaws" / law["acts_year"] / f"{law['chapter']}.json"
        if not path.exists():
            missing += 1
            continue
        html = json.loads(path.read_text("utf-8"))["ChapterText"]
        fixes = all_fixes.get(law["law_key"], {})
        law_rows, law_unread = read_law(law["law_key"], law["law_type"], html, fixes)
        for (section, printed), target in fixes.items():
            if not any(r["section"] == section and r["target_law_key"] == target for r in law_rows):
                print(f"  warning: citation fix {law['law_key']} §{section} ({printed}) not used")
        rows += law_rows
        if law["role"] == "in_scope":
            unread += law_unread
        else:
            reference_unread += len(law_unread)
        read += 1
    _write(ctx.interim_dir / "amendments_raw.csv", schemas.columns("amendments_raw"), rows)
    _write(ctx.reports_dir / "unread_sections.csv", UNREAD_COLUMNS, unread)
    print(f"  read {read} laws: {len(rows)} amendment rows, {len(unread)} unread sections")
    if reference_unread:
        print(f"  {reference_unread} unread sections in reference-only laws (not reported)")
    if missing:
        print(f"  {missing} laws on the law list have no cached text yet (run the laws stage)")
    return 0
