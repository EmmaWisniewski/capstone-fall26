"""File formats (DESIGN §7) and allowed values (DESIGN §9).

This module is the only place column lists and enums live in code. It must match
DESIGN §7 and §9; change both together and add a Decision Log entry (§20).

CSV value conventions (§7 preamble): money is an integer number of dollars, dates are
ISO ``YYYY-MM-DD``, booleans are ``true``/``false``, lists are ``;``-separated, and an
empty cell means null.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# §9 Allowed values
# ---------------------------------------------------------------------------

# §9.1
LAW_TYPES = ("gaa", "supplemental", "surplus", "bond", "interim", "other")

# §7.1 law list role. `tbd` marks a discovered candidate awaiting a human decision (§6 stage 1).
ROLES = ("in_scope", "reference_only", "excluded", "tbd")

PARSE_STRATEGIES = ("auto", "manual", "auto+manual")

# §9.2: code -> export label
FUNDING_ACTION_LABELS = {
    "ORIG": "Original appropriation",
    "NEW": "Supplemental appropriation",
    "INC": "Supplemental increase",
    "RED": "Supplemental reduction",
    "VETO": "Veto reduction",
    "OVR": "Veto override restoration",
    "INT": "Interim appropriation",
    "CAP": "Capital authorization",
    "REAUTH": "Reauthorization",
    "PAC": "Prior appropriation continued",
    "PURP": "Alteration of purpose",
    "XFER": "Transfer",
}
FUNDING_ACTIONS = tuple(FUNDING_ACTION_LABELS)

# §9.2 "counts toward total?" column. Defaults only; §10 caveats (ISF, federal, §2E) are applied
# in combine.
FUNDING_ACTION_COUNTS_TOWARD_TOTAL = {
    "ORIG": True,
    "NEW": True,
    "INC": True,
    "RED": True,
    "VETO": True,
    "OVR": True,
    "INT": False,
    "CAP": False,
    "REAUTH": False,
    "PAC": False,
    "PURP": False,
    "XFER": False,
}

# §9.3
AMOUNT_KINDS = (
    "appropriation",
    "retained_revenue_ceiling",
    "bond_authorization",
    "transfer",
    "delta",
    "prior_appropriation_continued",
    "interim",
    "none",
)

# §9.4
SECTION_TYPES = (
    "approp_main",
    "approp_new",
    "isf",
    "federal_grants",
    "trust_transfer",
    "surtax",
    "capital",
    "outside",
    "interim",
)

# §9.5
FLAGS = (
    "federal",
    "federal_mixed",
    "isf_chargeback",
    "trust_transfer",
    "fund_transfer_chain",
    "arpa_reallocation",
    "multi_year",
    "retained_revenue",
    "veto_unverified",
    "cthru_mismatch",
    "manual_row",
    "low_confidence_parse",
)

# §9.7
HUMAN_REVIEW_STATUSES = ("Not human reviewed", "Human reviewed")

# §9.8: exactly the values in policyareas.csv (note the typographic apostrophe)
POLICY_AREAS = (
    "Education",
    "Health and public health",
    "Children and families",
    "Human services and income support",
    "Housing and homelessness",
    "Economic development and workforce",
    "Transportation",
    "Environment and natural resources",
    "Public safety and corrections",
    "Courts and legal services",
    "Veterans’ services",
    "Arts, culture, and recreation",
    "Government administration and oversight",
    "General local aid",
    "Public employee pensions and benefits",
    "Debt service, reserves, and statewide finance",
    "Multiple",
    "Unclassified/other",
)

# §7.3 / §7.4 / §7.7 / §7.9 enums
CONFIDENCE_LEVELS = ("high", "medium", "low")
VETO_KINDS_INLINE = ("none", "disapproved", "reduced", "reduced_and_wording", "overridden")
ACTION_TYPES = (
    "figure_change",
    "item_insert",
    "item_strike",
    "item_replace",
    "text_insert",
    "text_strike",
    "date_extend",
    "purpose_change",
    "transfer",
    "direct_appropriation",
)
# §5.7 vetoes are netted into the amount; veto_status records what happened (Q4)
VETO_STATUSES = ("none", "vetoed", "reduced", "overridden", "unknown")
# §5.2 where a funding-action row's amount came from
AMOUNT_SOURCES = ("cthru", "law_text", "manual")
FY_RULES = ("stated", "target_act", "enactment_fy")
PROGRAM_PURPOSE_METHODS = ("rule", "human")
POLICY_AREA_METHODS = ("catalog", "department", "human")
PREVIOUSLY_FUNDED = ("Yes", "No", "Unknown")
ONE_TIME_OR_RECURRING = ("Recurring", "One-time", "Not classified")
NEW_OR_REAPPROP = ("New", "Re-appropriation", "Transfer of existing authority", "Pending")

# ---------------------------------------------------------------------------
# §7 File formats
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Col:
    """One CSV column. ``kind`` is str|int|float|date|bool|enum|list."""

    name: str
    kind: str = "str"
    enum: tuple[str, ...] | None = None
    required: bool = False


def _cols(*specs: Col | str) -> tuple[Col, ...]:
    return tuple(Col(s) if isinstance(s, str) else s for s in specs)


_READER = (Col("reader_version"), Col("confidence", "enum", CONFIDENCE_LEVELS))

SCHEMAS: dict[str, tuple[Col, ...]] = {
    # §7.1 config/law_list.csv
    "law_list": _cols(
        Col("law_key", required=True),
        Col("acts_year", "int", required=True),
        Col("chapter", required=True),
        Col("approved_date", "date", required=True),
        "approval_type",
        "api_title",
        "law_name",
        Col("law_type", "enum", LAW_TYPES),
        Col("role", "enum", ROLES, required=True),
        "include_reason",
        Col("primary_fy", "int"),
        "origin_bill",
        Col("parse_strategy", "enum", PARSE_STRATEGIES),
        "notes",
    ),
    # §7.3 data/interim/items_raw.csv
    "items_raw": _cols(
        Col("law_key", required=True),
        Col("section", required=True),
        "section_fund_default",
        Col("fy_stated", "int"),
        Col("para_start", "int", required=True),
        Col("para_end", "int", required=True),
        Col("line_item", required=True),
        "secretariat_header_raw",
        "agency_header_raw",
        "item_text",
        Col("amount", "int"),
        Col("amount_struck", "int"),
        Col("retained_revenue_ceiling", "int"),
        "fund_splits_raw",
        "veto_annotation_raw",
        Col("veto_kind_inline", "enum", VETO_KINDS_INLINE),
        *_READER,
    ),
    # §7.4 data/interim/amendments_raw.csv
    "amendments_raw": _cols(
        Col("law_key", required=True),
        Col("section", required=True),
        Col("action_type", "enum", ACTION_TYPES, required=True),
        "target_law_key",
        "target_section",
        "target_item",
        Col("old_figure", "int"),
        Col("new_figure", "int"),
        "old_date",
        "new_date",
        Col("amount", "int"),
        "from_item",
        "to_item",
        "fund_raw",
        "source_text",
        *_READER,
    ),
    # §7.5 data/interim/cthru_line_items.csv (one row per fiscal year x account, aggregated)
    "cthru_line_items": _cols(
        Col("fiscal_year", "int", required=True),
        Col("line_item", required=True),
        "account_name",
        "department_code",
        "department_name",
        "secretariat",
        "fund_numbers",
        Col("original_enacted", "int"),
        Col("supplemental", "int"),
        Col("retained_revenue_ceiling", "int"),
        Col("total_enacted", "int"),
    ),
}
# §7.3 data/interim/bond_items_raw.csv: same columns as items_raw (workstream A writes it)
SCHEMAS["bond_items_raw"] = SCHEMAS["items_raw"]

# §7.7 data/interim/funding_actions.csv (canonical)
FUNDING_ACTIONS_TABLE = _cols(
    Col("record_id", required=True),
    Col("law_key", required=True),
    Col("section", required=True),
    "line_item",
    Col("target_law_key", required=True),
    Col("event_date", "date", required=True),
    Col("calendar_year", "int", required=True),
    Col("fiscal_year", "int", required=True),
    Col("fy_rule", "enum", FY_RULES, required=True),
    Col("available_through", "date"),
    Col("section_type", "enum", SECTION_TYPES, required=True),
    Col("funding_action", "enum", FUNDING_ACTIONS, required=True),
    Col("amount_kind", "enum", AMOUNT_KINDS, required=True),
    Col("amount", "int"),
    Col("amount_source", "enum", AMOUNT_SOURCES, required=True),
    Col("amount_printed", "int"),
    Col("veto_status", "enum", VETO_STATUSES),
    Col("counts_toward_total", "bool", required=True),
    "fund_primary",
    Col("federal_share", "float"),
    Col("flags", "list", FLAGS),
    "agency_header_raw",
    "item_text",
    "source_url",
    Col("source_para_start", "int"),
    "reader_version",
)
SCHEMAS["funding_actions"] = FUNDING_ACTIONS_TABLE

# §7.6 config/manual_rows.csv: funding_actions columns minus record_id, plus provenance
SCHEMAS["manual_rows"] = (
    *(c for c in FUNDING_ACTIONS_TABLE if c.name != "record_id"),
    Col("source_quote", required=True),
    Col("entered_by", required=True),
    Col("entered_on", "date", required=True),
)

# §7.8 side tables
SCHEMAS["fund_splits"] = _cols(
    Col("record_id", required=True),
    Col("fund_name", required=True),
    "fund_number",
    Col("share", "float", required=True),
    Col("is_federal", "bool", required=True),
)
SCHEMAS["running_amounts"] = _cols(
    Col("target_law_key", required=True),
    Col("section", required=True),
    Col("line_item", required=True),
    Col("as_of_event", required=True),
    Col("amount_after", "int"),
)

# §7.9 data/interim/labels.csv
SCHEMAS["labels"] = _cols(
    Col("record_id", required=True),
    "agency_office",
    "program_purpose",
    Col("program_purpose_method", "enum", PROGRAM_PURPOSE_METHODS),
    Col("policy_area", "enum", POLICY_AREAS),
    Col("policy_area_method", "enum", POLICY_AREA_METHODS),
    Col("previously_funded", "enum", PREVIOUSLY_FUNDED),
    Col("one_time_or_recurring", "enum", ONE_TIME_OR_RECURRING),
    Col("new_or_reapprop", "enum", NEW_OR_REAPPROP),
)

# §7.10 config/line_item_catalog.csv (human-curated; carries labels from year to year)
SCHEMAS["line_item_catalog"] = _cols(
    Col("line_item", required=True),
    Col("policy_area", "enum", POLICY_AREAS, required=True),
    Col("label_every_year", "bool", required=True),
    "decided_by",
    Col("decided_on", "date"),
    "note",
)

# §7.10 config/department_policy_areas.csv (human-curated; rule for items not yet in the catalog)
SCHEMAS["department_policy_areas"] = _cols(
    Col("department_code", required=True),
    "department_name",
    Col("policy_area", "enum", POLICY_AREAS),
    Col("mixed", "bool", required=True),
    "decided_by",
    Col("decided_on", "date"),
    "note",
)

# §7.11 review/corrections.csv (human-edited)
SCHEMAS["corrections"] = _cols(
    Col("record_id", required=True),
    Col("field", required=True),
    "new_value",
    "expected_old_value",
    Col("reviewer", required=True),
    Col("review_date", "date", required=True),
    "note",
)

# §7.14 config/funds.csv (human-curated; drives the federal flag, §9.5)
SCHEMAS["funds"] = _cols(
    Col("fund_name", required=True),
    "fund_number",
    Col("is_federal", "bool", required=True),
    "notes",
)

# §7.12 review/review_queue.csv: fixed leading columns, then free context columns
REVIEW_QUEUE_LEADING = _cols(
    Col("record_id", required=True),
    Col("reason", required=True),
    Col("priority", "int"),
)

# §7.2 data/interim/paragraphs/{law_key}.jsonl keys
PARAGRAPH_KEYS = ("law_key", "para_idx", "text", "raw_html", "classes", "struck", "bold", "links")

# §7.13 / §8: the export uses exactly these 19 columns, in this order (exampledata.csv)
EXPORT_COLUMNS = (
    "Record ID",
    "Law citation",
    "Law name",
    "Enactment date",
    "Calendar year",
    "Fiscal year",
    "Section",
    "Line item",
    "Agency / office",
    "Program / purpose",
    "Policy area",
    "Funding action",
    "Appropriation/change ($)",
    "Previously funded?",
    "One-time or recurring funding",
    "New funding appropriation or re-appropriation of existing funding?",
    "Human review status",
    "Source URL",
    "Source or calculation for total",
)


def columns(table: str) -> list[str]:
    return [c.name for c in SCHEMAS[table]]


# ---------------------------------------------------------------------------
# §9.6 Record ID and law key
# ---------------------------------------------------------------------------

LAW_KEY_RE = re.compile(r"^(\d{4})-(\d+)$")
LINE_ITEM_RE = re.compile(r"^\d{4}-\d{4}$")
RECORD_ID_RE = re.compile(
    r"^(?P<acts_year>\d{4})-(?P<chapter>\d{3,})-S(?P<section>[0-9A-Z]+)"
    r"-(?P<line_item>\d{4}-\d{4}|NOITEM)-(?P<funding_action>[A-Z]+)-(?P<ordinal>[1-9]\d*)$"
)


def law_key(acts_year: int, chapter: int | str) -> str:
    return f"{int(acts_year)}-{int(chapter)}"


def record_id_prefix(
    acts_year: int, chapter: int | str, section: str, line_item: str | None, funding_action: str
) -> str:
    if funding_action not in FUNDING_ACTION_LABELS:
        raise ValueError(f"unknown funding_action {funding_action!r}")
    if line_item and not LINE_ITEM_RE.match(line_item):
        raise ValueError(f"line_item must be NNNN-NNNN, got {line_item!r}")
    item = line_item or "NOITEM"
    return f"{int(acts_year)}-{int(chapter):03d}-S{section}-{item}-{funding_action}"


def assign_record_ids(prefixes: Iterable[str]) -> list[str]:
    """Append ordinals to prefixes given in source order (§9.6). Deterministic."""
    seen: dict[str, int] = {}
    out = []
    for p in prefixes:
        seen[p] = seen.get(p, 0) + 1
        out.append(f"{p}-{seen[p]}")
    return out


# ---------------------------------------------------------------------------
# Validation helpers (used by `validate`, check 1 in §13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Problem:
    table: str
    row: int  # 1-based data row; 0 for header problems
    column: str
    message: str


def _check_value(col: Col, value: str) -> str | None:
    if value == "":
        return "required value is empty" if col.required else None
    if col.kind == "int":
        if not re.fullmatch(r"-?\d+", value):
            return f"not an integer: {value!r}"
    elif col.kind == "float":
        try:
            float(value)
        except ValueError:
            return f"not a number: {value!r}"
    elif col.kind == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            return f"not an ISO date: {value!r}"
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return f"not YYYY-MM-DD: {value!r}"
    elif col.kind == "bool":
        if value not in ("true", "false"):
            return f"bool must be true/false: {value!r}"
    elif col.kind == "enum":
        if value not in (col.enum or ()):
            return f"{value!r} not an allowed value"
    elif col.kind == "list":
        bad = [v for v in value.split(";") if v not in (col.enum or ())]
        if bad:
            return f"{bad!r} not an allowed value"
    return None


def validate_rows(
    table: str, header: list[str], rows: Iterable[Mapping[str, str]]
) -> list[Problem]:
    expected = columns(table)
    if header != expected:
        missing = [c for c in expected if c not in header]
        extra = [c for c in header if c not in expected]
        msg = f"header mismatch; missing={missing} extra={extra}"
        if not missing and not extra:
            msg = "header columns out of order"
        return [Problem(table, 0, "", msg)]
    problems = []
    for i, row in enumerate(rows, start=1):
        for col in SCHEMAS[table]:
            err = _check_value(col, row.get(col.name) or "")
            if err:
                problems.append(Problem(table, i, col.name, err))
    return problems


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def validate_file(table: str, path: Path) -> list[Problem]:
    header, rows = read_csv(path)
    return validate_rows(table, header, rows)
