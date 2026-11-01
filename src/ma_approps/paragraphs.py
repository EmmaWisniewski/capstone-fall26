"""Shared helper: law HTML to an ordered list of paragraphs (DESIGN §7.2, §11.1).

Owner: workstream B (Supplemental budgets). Not a stage: read_items, read_bonds and
read_amendments all call it, so its output (schemas.PARAGRAPH_KEYS) is a fixed format (DESIGN §7.2).

Each paragraph is a dict:
- ``law_key``: e.g. ``2023-28``
- ``para_idx``: 0-based position among the law's non-empty paragraphs (deterministic)
- ``text``: normalized text (§11.1); smart quotes are kept, use ``key()`` for matching
- ``raw_html``: the source HTML the paragraph came from, for debugging
- ``classes``: CSS classes on the paragraph's elements (don't rely on them, §11.1)
- ``struck``: struck-through runs of text, in order (veto evidence)
- ``bold``: bold runs of text, in order (veto notes are bold)
- ``links``: hrefs of links in the paragraph, in order

Paragraph boundaries are block elements (``p``, ``div``, ``h1``–``h6``, ``center``, ``li``, …),
``<br>`` and ``<hr>``. A table row is one paragraph with its cells joined by `` | ``.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

# Tags that end the current paragraph when they open or close
BLOCK_TAGS = frozenset(
    "p div h1 h2 h3 h4 h5 h6 center li ul ol blockquote table tbody thead tfoot tr pre".split()
)
BREAK_TAGS = frozenset(("br", "hr"))
VOID_TAGS = frozenset(("br", "hr", "img", "meta", "link", "input", "wbr"))
STRIKE_TAGS = frozenset(("s", "strike", "del"))
BOLD_TAGS = frozenset(("strong", "b"))
CELL_TAGS = frozenset(("td", "th"))

# Hyphen-like characters NFKC leaves alone; inside an item ID (NNNN-NNNN) they mean "-"
_DASHES = "‐‑‒–—−"
_ID_DASH_RE = re.compile(rf"(?<!\d)(\d{{4}})[{_DASHES}](\d{{4}})(?!\d)")
_SPACE_RE = re.compile(r"\s+")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def normalize(text: str) -> str:
    """§11.1 text normalization: NFKC, non-breaking spaces, dashes in item IDs, whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _ID_DASH_RE.sub(r"\1-\2", text)
    return _SPACE_RE.sub(" ", text).strip()


def key(text: str) -> str:
    """Matching key: ``text`` with smart quotes made plain. Use for regexes, never for display."""
    return text.translate(_QUOTES)


def _style_struck(style: str) -> bool:
    return "line-through" in style.replace(" ", "").lower()


def _style_bold(style: str) -> bool:
    s = style.replace(" ", "").lower()
    return "font-weight:bold" in s or "font-weight:700" in s


def _runs(chars: list[tuple[str, bool]]) -> list[str]:
    """Contiguous flagged runs of text, normalized, empties dropped."""
    out, buf = [], []
    for ch, flag in [*chars, ("", False)]:
        if flag:
            buf.append(ch)
        elif buf:
            run = normalize("".join(buf))
            if run:
                out.append(run)
            buf = []
    return out


class _Parser(HTMLParser):
    def __init__(self, law_key: str, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.law_key = law_key
        self.html = html
        self._line_starts = [0]
        for m in re.finditer("\n", html):
            self._line_starts.append(m.end())
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, struck, bold)
        self.out: list[dict[str, Any]] = []
        self.in_row = 0
        self._reset(0)

    # -- positions -------------------------------------------------------
    def _offset(self) -> int:
        line, col = self.getpos()
        return self._line_starts[line - 1] + col

    def _tag_end(self) -> int:
        start = self._offset()
        text = self.get_starttag_text()
        return start + len(text) if text else self.html.find(">", start) + 1

    # -- paragraph buffer ------------------------------------------------
    def _reset(self, start: int) -> None:
        self.chars: list[tuple[str, bool, bool]] = []
        self.classes: list[str] = []
        self.links: list[str] = []
        self.start = start

    def _flush(self, end: int) -> None:
        text = normalize("".join(c for c, _, _ in self.chars))
        if text:
            self.out.append(
                {
                    "law_key": self.law_key,
                    "para_idx": len(self.out),
                    "text": text,
                    "raw_html": self.html[self.start : end].strip(),
                    "classes": self.classes,
                    "struck": _runs([(c, s) for c, s, _ in self.chars]),
                    "bold": _runs([(c, b) for c, _, b in self.chars]),
                    "links": self.links,
                }
            )
        self._reset(end)

    def _boundary(self, at: int, resume: int) -> None:
        """End the paragraph at ``at``; the next one starts at ``resume``."""
        if self.in_row:
            return
        self._flush(at)
        self.start = resume

    # -- HTMLParser hooks ------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        here, after = self._offset(), self._tag_end()
        if tag in BREAK_TAGS:
            self._boundary(here, after)
            return
        if tag in BLOCK_TAGS and tag != "tr":
            self._boundary(here, here)
        if tag == "tr":
            self._boundary(here, here)
            self.in_row += 1
        if tag in CELL_TAGS and self.chars:
            self.chars.append((" | ", False, False))
        for c in a.get("class", "").split():
            if c not in self.classes:
                self.classes.append(c)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in VOID_TAGS:
            return
        struck, bold = self._state()
        style = a.get("style", "")
        self.stack.append(
            (
                tag,
                struck or tag in STRIKE_TAGS or _style_struck(style),
                bold or tag in BOLD_TAGS or _style_bold(style),
            )
        )

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        here = self._offset()
        after = self.html.find(">", here) + 1 or len(self.html)
        # Pop to the matching open tag; ignore stray end tags
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag == "tr" and self.in_row:
            self.in_row -= 1
            self._boundary(after, after)
        elif tag in BLOCK_TAGS:
            self._boundary(after, after)

    def handle_data(self, data: str) -> None:
        struck, bold = self._state()
        self.chars.extend((ch, struck, bold) for ch in data)

    def _state(self) -> tuple[bool, bool]:
        return (self.stack[-1][1], self.stack[-1][2]) if self.stack else (False, False)

    def close(self) -> None:
        super().close()
        self.in_row = 0
        self._flush(len(self.html))


def paragraphs(law_key: str, chapter_html: str) -> list[dict[str, Any]]:
    """Split a law's ``ChapterText`` HTML into paragraphs (DESIGN §7.2). Deterministic."""
    p = _Parser(law_key, chapter_html)
    p.feed(chapter_html)
    p.close()
    return p.out
