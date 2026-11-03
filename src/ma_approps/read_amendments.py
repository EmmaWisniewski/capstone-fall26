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

This stage only records what each law says. The running amounts table and the struck-figure check
(§5.5) need dates and CTHRU amounts, so they belong in `combine` and `validate`.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ma_approps import paragraphs, schemas
from ma_approps.context import Context

IMPLEMENTED = True
READER_VERSION = "0.1.0"

UNREAD_COLUMNS = ("law_key", "section", "reason", "text", "explanation")

# Sections 2, 2A … 2I of these law types hold line items, which read_items / read_bonds read.
APPROP_LAW_TYPES = ("gaa", "supplemental", "surplus", "bond")
APPROP_SECTION_RE = re.compile(r"^2[A-Z]*$")

ITEM = r"\d{4}-\d{4}"
DATE = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r" \d{1,2}, \d{4}"
)

SECTION_START_RE = re.compile(r"^SECTION\s+(\d+[A-Z]*)\b\.?\s*")
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
FUND_RE = re.compile(r"\bfrom the ((?:[A-Z][\w’'&.-]*\s+)+?Fund)\b")
MONEY_RE = re.compile(r"\$\s*\d")
ITEM_OR_APPROP_RE = re.compile(rf"\bitems?\s+{ITEM}|appropriat", re.I)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _key(text: str) -> str:
    """Matching form of a paragraph (§11.1): plain quotes and plain hyphens in item IDs."""
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    return re.sub(r"(\d{4})[‐‑–—](\d{4})", r"\1-\2", text)


def _simple_paragraphs(law_key: str, html: str) -> list[dict[str, Any]]:
    """Stand-in for paragraphs.paragraphs() (workstream B) until it exists, in the §7.2 format.

    Only ``text`` and ``para_idx`` are used here, so struck, bold and links are left empty.
    """
    soup = BeautifulSoup(html, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    out: list[dict[str, Any]] = []
    for p in soup.find_all("p"):
        for line in p.get_text().split("\n"):
            text = _normalize(line)
            if text:
                out.append(
                    {
                        "law_key": law_key,
                        "para_idx": len(out),
                        "text": text,
                        "raw_html": str(p),
                        "classes": p.get("class") or [],
                        "struck": [],
                        "bold": [],
                        "links": [],
                    }
                )
    return out


def _paragraphs(law_key: str, html: str) -> list[dict[str, Any]]:
    try:
        return paragraphs.paragraphs(law_key, html)
    except NotImplementedError:
        return _simple_paragraphs(law_key, html)


def _sections(paras: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Group paragraphs into (section number, paragraph texts), in source order."""
    out: list[tuple[str, list[str]]] = []
    for p in paras:
        m = SECTION_START_RE.match(p["text"])
        if m:
            out.append((m[1], [p["text"]]))
        elif out:
            out[-1][1].append(p["text"])
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
        m = re.match(rf"({ITEM})\b", text)
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
            return [
                {
                    "action_type": "item_replace",
                    "target_item": i,
                    "new_figure": new.get(i),
                    "confidence": "high" if new.get(i) is not None else "low",
                }
                for i in struck
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
        # "both times it appears", "in line 7", "in each instance": an earmark inside the text,
        # not necessarily the item's appropriation; combine's struck-figure check confirms it.
        qualified = m["line"] or m["each"] or m["where"].strip(" ,")
        action = {
            "action_type": "figure_change",
            "old_figure": _int(m["old"]),
            "new_figure": _int(m["new"]),
            "confidence": "low" if qualified else "high",
        }
    elif m := YEAR_FIGURE_RE.search(predicate):
        action = {"action_type": "date_extend", "old_date": m["old"], "new_date": m["new"]}
    elif m := DATE_WORDS_RE.search(predicate):
        action = {
            "action_type": "date_extend",
            "old_date": _iso(m["old"]),
            "new_date": _iso(m["new"]),
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


def _sentence_actions(law_key: str, section: str, full: str) -> list[dict[str, Any]]:
    """Direct appropriations and transfers in a section that does not amend another law."""
    actions = []
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z])", full):
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
            from_item = re.match(rf"items?\s+({ITEM})", m["tail"])
            to_item = re.search(rf"\bto\s+items?\s+({ITEM})", m["tail"])
            actions.append(
                {
                    "action_type": "transfer",
                    "amount": _int(m["amount"]),
                    "from_item": from_item[1] if from_item else None,
                    "to_item": to_item[1] if to_item else None,
                    "fund_raw": fund[1] if fund else None,
                    # fund-to-fund transfers carry no items; a human should confirm them
                    "confidence": "high" if from_item and to_item else "medium",
                }
            )
    return actions


def read_law(law_key: str, law_type: str, html: str) -> tuple[list[dict], list[dict]]:
    """amendments_raw rows and unread_sections rows for one law, in source order."""
    rows: list[dict] = []
    unread: list[dict] = []
    chapters: dict[str, str] = {}
    last: dict[str, Any] = {"law": None, "section": None}
    for section, texts in _sections(_paragraphs(law_key, html)):
        keyed = [_key(t) for t in texts]
        full = "\n".join(keyed)
        if law_type in APPROP_LAW_TYPES and APPROP_SECTION_RE.match(section):
            _remember_chapters(full, chapters)
            continue

        actions: list[dict[str, Any]] = []
        reason = None
        target = None
        body = SECTION_START_RE.sub("", keyed[0], count=1)
        m = None if body.startswith("Notwithstanding") else AMENDED_RE.match(body)
        if m:
            target = _resolve(AS_AMENDED_RE.sub("", m["subject"]), law_key, chapters, last)
            if target is None:
                reason = "could not tell which law this section amends"
            elif target[0] != "GL":
                predicate = AS_AMENDED_RE.sub("", m["predicate"])
                found = _amendment_actions(predicate, target[2], keyed[1:])
                if found is None:
                    reason = "changes a line item in a way no pattern recognises"
                else:
                    actions = [
                        {"target_law_key": target[0], "target_section": target[1], **a}
                        for a in found
                    ]
                last = {"law": target[0], "section": target[1]}
        else:
            actions = _sentence_actions(law_key, section, full)

        general_laws = target is not None and target[0] == "GL"
        if not actions and not reason and not general_laws:
            if MONEY_RE.search(full) and ITEM_OR_APPROP_RE.search(full):
                reason = "mentions dollars and an item or appropriation but matched no pattern"
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
