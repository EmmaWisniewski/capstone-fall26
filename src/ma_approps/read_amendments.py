"""Stage 5 `read_amendments`: outside sections to data/interim/amendments_raw.csv (DESIGN §7.4,
§11.3).

Owner: workstream C (Amendments). Reads every cached law on the law list and, in each outside
section (any section other than the §2… appropriation sections), recognises the §11.3 patterns:
figure changes, date extensions, item insertions, replacements and strikes, text-only changes,
transfers and direct appropriations. Interim ("1/12th") budgets are direct appropriations, so they
are read here rather than typed by hand. "Said item … of said section 2 of said chapter 28" is
resolved by carrying the last named law, section and item forward.

An outside section that mentions dollars and an item or appropriation but matches no pattern goes
to reports/unread_sections.csv for a human to explain (§13.6).

An outside section that looks vetoed (struck-through text, or a "Governor disapproved of the
following section" note) is still read, but its rows get `low` confidence and it is listed in
reports/unread_sections.csv so a human checks whether the Legislature overrode the veto. Inline
veto markup is a hint, not truth (§11.4).

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

from ma_approps import paragraphs, schemas
from ma_approps.context import Context

IMPLEMENTED = True
READER_VERSION = "0.5.0"

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
CHAPTER_RE = re.compile(
    r"\b(said\s+)?chapter\s+(\d+[A-Z]*)"
    r"(?:\s+of\s+the\s+acts\s+of\s+(\d{4})|\s+of\s+the\s+(General\s+Laws))?",
    re.I,
)
ITEMS_RE = re.compile(rf"items?\s+({ITEM}(?:(?:,\s*|,?\s+and\s+){ITEM})*)")

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
FUND_RE = re.compile(r"\bfrom the ((?:[A-Z][\w’'&.-]*\s+)+?Fund)\b")
# A fund named as a transfer's source, even in lowercase: "the federal COVID-19 response fund"
FUND_NAME_RE = re.compile(
    r"\bthe ((?:(?!(?:the|of|in|or|and|to|from|by|for|established|section|chapter|item)\b)"
    r"[\w’'&.-]+ ){0,6}?[Ff]und)\b"
)
MONEY_RE = re.compile(r"\$\s*\d")
ITEM_OR_APPROP_RE = re.compile(rf"\bitems?\s+{ITEM}|appropriat", re.I)
# Printed just before what it is about: "The Governor disapproved of the following section, …",
# "Governor returned the following section with recommendation of amendment, …"
GOVERNOR_NOTE_RE = re.compile(r"^(?:The )?Governor (?:disapproved|returned)\b")


def _sections(paras: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group paragraphs into sections, in source order: ``section``, ``texts`` and ``vetoed``.

    A Governor's note comes just before what it is about, so it is held back: before a new
    section it only marks that section, and anywhere else it stays in place in the text. A section
    is ``vetoed`` if any of its text is struck through or a note says the Governor disapproved.
    """
    out: list[dict[str, Any]] = []
    notes: list[str] = []
    for p in paras:
        if GOVERNOR_NOTE_RE.match(p["text"]):
            notes.append(p["text"])
            continue
        if m := SECTION_START_RE.match(p["text"]) or SECTION2_HEADING_RE.match(p["text"]):
            out.append({"section": m[1].upper(), "texts": [], "vetoed": False})
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


def _iso(day: str) -> str:
    return datetime.strptime(day, "%B %d, %Y").date().isoformat()


def _chapter_law(m: re.Match, chapters: dict[str, str]) -> str | None:
    """Law key for a chapter mention; "GL" for the General Laws; None if unknown."""
    if m[3]:
        return schemas.law_key(m[3], m[2])
    if m[4]:
        return "GL"
    if m[1]:
        return chapters.get(m[2])
    return None


def _remember_chapters(text: str, chapters: dict[str, str]) -> None:
    """Record every explicit chapter mention so a later "said chapter N" can be resolved."""
    for m in CHAPTER_RE.finditer(text):
        if m[3] or m[4]:
            chapters[m[2]] = _chapter_law(m, chapters)


def _resolve(
    subject: str, law_key: str, chapters: dict[str, str], last: dict[str, Any]
) -> tuple[str, str | None, list[str]] | None:
    """(target law key, target section, items) named by an amendment's subject, or None."""
    items = re.findall(ITEM, subject) if re.match(r"(?:said\s+)?items?\b", subject, re.I) else []
    sec = re.search(r"\bsection\s+(\d+[A-Z]*)\b", subject, re.I)
    ch = CHAPTER_RE.search(subject)
    if "of this act" in subject:
        law = law_key
    elif ch:
        law = _chapter_law(ch, chapters)
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
    elif re.search(r"\bstriking out\b.*\binserting in place thereof\b", predicate):
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
        for m in TRANSFER_RE.finditer(sentence):
            # the source is everything before the first "to": "the prescription advantage
            # program in line-item 9110-1455 … and the Health Safety Net Trust Fund … to support"
            source = re.split(r"\bto\b", m["tail"], maxsplit=1)[0]
            from_item = re.search(rf"\bitems?\s+({ITEM})", source)
            to_item = re.search(rf"\bto\s+(?:line-)?items?\s+({ITEM})", m["tail"])
            funds = list(dict.fromkeys(FUND_NAME_RE.findall(source)))
            actions.append(
                {
                    "action_type": "transfer",
                    "amount": _int(m["amount"]),
                    "from_item": from_item[1] if from_item else None,
                    "to_item": to_item[1] if to_item else None,
                    "fund_raw": "; ".join(funds) or None,
                    # fund-to-fund transfers carry no items; a human should confirm them
                    "confidence": "high" if from_item and to_item else "medium",
                }
            )
        for m in TRANSFER_FROM_RE.finditer(sentence):
            from_item = re.search(rf"\bitems?\s+({ITEM})", m["source"])
            to_item = re.search(rf"\bitems?\s+({ITEM})", m["dest"])
            funds = list(dict.fromkeys(FUND_NAME_RE.findall(m["source"])))
            # "the greater of $45,000,000 or 1/12 of …": the stated figure is only a bound
            bound = m["qual"] in ("the greater of ", "the lesser of ")
            actions.append(
                {
                    "action_type": "transfer",
                    "amount": _int(m["amount"]),
                    "from_item": from_item[1] if from_item else None,
                    "to_item": to_item[1] if to_item else None,
                    "fund_raw": "; ".join(funds) or None,
                    "confidence": "low"
                    if bound
                    else ("high" if from_item and to_item else "medium"),
                }
            )
    return actions


def read_law(law_key: str, law_type: str, html: str) -> tuple[list[dict], list[dict]]:
    """amendments_raw rows and unread_sections rows for one law, in source order."""
    rows: list[dict] = []
    unread: list[dict] = []
    chapters: dict[str, str] = {}
    last: dict[str, Any] = {"law": None, "section": None}
    for s in _sections(paragraphs.paragraphs(law_key, html)):
        section, texts = s["section"], s["texts"]
        keyed = [paragraphs.key(t) for t in texts]
        full = "\n".join(keyed)
        if law_type in APPROP_LAW_TYPES and APPROP_SECTION_RE.match(section):
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
        if not actions and not reason and not general_laws:
            if MONEY_RE.search(full) and ITEM_OR_APPROP_RE.search(full):
                reason = "mentions dollars and an item or appropriation but matched no pattern"
        if actions and s["vetoed"]:
            reason = "looks vetoed (struck text or a veto note); check whether it was overridden"
        if reason:
            unread.append(
                {"law_key": law_key, "section": section, "reason": reason, "text": texts[0][:500]}
            )
        for a in actions:
            rows.append(
                {
                    "law_key": law_key,
                    "section": section,
                    "source_text": "\n".join(texts),
                    "reader_version": READER_VERSION,
                    "confidence": "high",
                    **a,
                    **({"confidence": "low"} if s["vetoed"] else {}),
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


def run(ctx: Context) -> int:
    _, laws = schemas.read_csv(ctx.config_dir / "law_list.csv")
    laws = [r for r in laws if r["role"] in ("in_scope", "reference_only")]
    if ctx.law:
        laws = [r for r in laws if r["law_key"] == ctx.law]
    rows: list[dict] = []
    unread: list[dict] = []
    read, missing = 0, 0
    for law in sorted(laws, key=lambda r: (int(r["acts_year"]), int(r["chapter"]))):
        path = ctx.raw_dir / "sessionlaws" / law["acts_year"] / f"{law['chapter']}.json"
        if not path.exists():
            missing += 1
            continue
        html = json.loads(path.read_text("utf-8"))["ChapterText"]
        law_rows, law_unread = read_law(law["law_key"], law["law_type"], html)
        rows += law_rows
        unread += law_unread
        read += 1
    _write(ctx.interim_dir / "amendments_raw.csv", schemas.columns("amendments_raw"), rows)
    _write(ctx.reports_dir / "unread_sections.csv", UNREAD_COLUMNS, unread)
    print(f"  read {read} laws: {len(rows)} amendment rows, {len(unread)} unread sections")
    if missing:
        print(f"  {missing} laws on the law list have no cached text yet (run the laws stage)")
    return 0
