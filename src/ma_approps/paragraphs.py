"""Shared helper: law HTML to an ordered list of paragraphs (DESIGN §7.2, §11.1).

Stub. Owner: workstream B (Supplemental budgets). Not a stage: read_items, read_bonds and
read_amendments all call it, so its output format (schemas.PARAGRAPH_KEYS) is a contract.
"""

from __future__ import annotations

from typing import Any


def paragraphs(law_key: str, chapter_html: str) -> list[dict[str, Any]]:
    raise NotImplementedError
