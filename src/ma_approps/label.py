"""Stage 7 `label`: agency, purpose, policy area and yes/no columns to labels.csv
(DESIGN §7.9, §8, §12).

Owner: workstream D (Labels). No LLM.

- Agency / office (§8 column 9): the office the law text says the line pays for ("For the
  operation of the division of marine fisheries" gives "Division of Marine Fisheries"), else an
  office named at the start of the CTHRU account name, else the line's CTHRU department that
  fiscal year, else the law's printed agency header (or, when that header is just "Office of
  the Secretary" or missing, the secretariat header above it, read from items_raw /
  bond_items_raw). A header inherited from another department is replaced by the department
  that owns the line item's first four digits in CTHRU.
- Program / purpose (§8 column 10): the first clause of the law text with boilerplate like "For
  the operation of" removed, else the CTHRU account name.
- Policy area (§12): config/line_item_catalog.csv, then config/department_policy_areas.csv
  (via the line's CTHRU department that fiscal year), else empty, which sends the row to the
  review queue.
- Previously funded? (§8 column 14, Q3): ``Yes`` if the line had non-zero enacted authority in
  the fiscal year before the row's, else ``No``.
- One-time or recurring (§8 column 15, Q3): a GAA row is ``Recurring`` if the line was also in
  the GAA the year before or the year after, else ``One-time``. Supplemental and bond rows are
  ``One-time`` (interim rule).
- New vs. re-appropriation stays ``Pending`` until the partner answers Q3.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from ma_approps import schemas
from ma_approps.context import Context

# Off until `combine` and `cthru` write the files this stage reads; run() fails without them.
IMPLEMENTED = False

# Funding actions that add or remove enacted authority (§9.2). Reauthorizations, transfers,
# purpose changes and interim budgets don't fund a line on their own.
AUTHORITY_ACTIONS = frozenset(("ORIG", "NEW", "INC", "RED", "VETO", "OVR", "CAP"))
ONE_TIME_ACTIONS = frozenset(("NEW", "INC", "RED", "CAP"))

Row = Mapping[str, str]


def _int(value: str | None) -> int:
    return int(value) if value else 0


# ---------------------------------------------------------------------------
# Agency / office and Program / purpose (§8 columns 9-10)
# ---------------------------------------------------------------------------

SMALL_WORDS = frozenset("a an and at by for in of on the to with".split())
UNIT = r"(?:division|office|bureau|board|commission|department)"

# "For the operation of the ..." and its variants, up to the thing the line pays for
_LEAD = re.compile(
    r"^for\s+(?:the\s+)?(?:(?:(?:maintenance|administration|operation)\s+and\s+)?"
    r"(?:operations?|administration|maintenance|administrative\s+expenses)\s+of\s+)?",
    re.I,
)
_UNIT_IN_TEXT = re.compile(rf"^({UNIT}\s+(?:of|on|for)\s+.+)$", re.I)
# Where an office's name ends and the rest of the sentence begins
_NAME_END = re.compile(
    r",?\s+(?:which|who|that|to|in\s+order|associated|including|with|by|from|within|under|"
    r"established|notwithstanding|subject|as)\b|\s+for\s+(?:the\s+)?(?:sole\s+)?(?:purposes?|"
    r"certification|costs?|expenses?|administration|implementation)\b",
    re.I,
)  # a bare comma isn't an end: "commission on lesbian, gay, bisexual, ..."
# Office names at the start of a CTHRU account name: "DIV.OF MARINE FISHERIES-ADMINISTRATION"
_UNIT_IN_ACCOUNT = re.compile(r"^(div(?:ision)?\.?|office|bureau)\s*(of|on|for)\s+(.+)$", re.I)
_ACCOUNT_SUFFIX = re.compile(
    r"\s*(?:-.*|\b(?:administration|admin|operations|rr|it|isf)\b.*)$", re.I
)
CTHRU_NAME_LIMIT = 60  # CTHRU cuts account names at 60 characters
_VAGUE_HEADER = re.compile(r"^Office of the (?:Secretary|Commissioner|Director)$", re.I)
# A division named without its parent, e.g. "Highway Division" under MassDOT
_BARE_DIVISION = re.compile(r"^(?!.*\bof\b)[\w&' ]+ Division$", re.I)

# Fixes for CTHRU department names that title case alone doesn't repair
DEPARTMENT_NAME_FIXES = (
    (r"^Sheriff Department (\w+)$", r"\1 Sheriff's Department"),
    (r"^Sheriffs Department Association$", "Massachusetts Sheriffs' Association"),
    (r"^Department Conservation\b", "Department of Conservation"),
    (r"^Governors Office$", "Governor's Office"),
    (r"^State Auditors Office$", "State Auditor's Office"),
    (r"^Attorney General Office$", "Attorney General's Office"),
    (r"^Campaign & Political Finance$", "Office of Campaign and Political Finance"),
    (r"^Commission on Status of Women$", "Commission on the Status of Women"),
    (r"^Mass (Commission for the Blind|Rehabilitation Commission)$", r"Massachusetts \1"),
    (r"^Mass Bay Community College$", "MassBay Community College"),
    (r"^Mt Wachusett\b", "Mount Wachusett"),
    (r"\bTech Comm College$", "Technical Community College"),
)


def title_case(name: str) -> str:
    """Title case for agency names. ALL-CAPS words are lowered first; mixed-case words, like
    proper nouns in the law text ("African Americans"), are kept."""
    words = name.split()
    out = []
    for i, word in enumerate(words):
        if word.isupper() or word.islower():
            word = word.lower()
            if i == 0 or word not in SMALL_WORDS:
                word = re.sub(r"[a-z]", lambda m: m.group(0).upper(), word, count=1)
        out.append(word)
    return " ".join(out)


def first_clause(text: str) -> str:
    """The start of a line's law text, up to its first semicolon, proviso, list or amount."""
    text = re.sub(r"^\d{4}-\d{4}\W*", "", text.strip())
    ends = (
        r";|,\s*provided\b|\s+provided\s+(?:further,?\s+)?that\b|,\s+including\b|,?\s+which\s+may\b"
        r"|\.{2,}|\$\d"
    )
    return re.split(ends, text, maxsplit=1)[0].strip(" ,.")


def _drop_lead(clause: str) -> str:
    return re.sub(r"^the\s+", "", _LEAD.sub("", clause, count=1), flags=re.I)


def agency_from_text(text: str) -> str:
    clause = first_clause(text)
    if not clause.lower().startswith("for "):
        return ""
    m = _UNIT_IN_TEXT.match(_drop_lead(clause))
    if not m:
        return ""
    unit, rest = re.match(rf"({UNIT}\s+(?:of|on|for)\s+)(.+)$", m.group(1), re.I).groups()
    return title_case(unit + _NAME_END.split(rest, maxsplit=1)[0].strip())


def agency_from_account(name: str) -> str:
    m = _UNIT_IN_ACCOUNT.match(name.strip())
    if not m or len(name) >= CTHRU_NAME_LIMIT:
        return ""
    kind = "Division" if m.group(1).lower().startswith("div") else m.group(1)
    rest = _ACCOUNT_SUFFIX.sub("", m.group(3)).strip()
    if not rest or rest.split()[-1].lower() in SMALL_WORDS:  # cut off mid-name: "... FINANCE AND"
        return ""
    return title_case(f"{kind} {m.group(2)} {rest}")


def department_display_name(name: str) -> str:
    name = re.sub(r"^the\s+", "", name.strip().rstrip("."), flags=re.I)
    name = title_case(name)
    for pattern, repl in DEPARTMENT_NAME_FIXES:
        name = re.sub(pattern, repl, name)
    return name


def header_agency(agency_header: str, secretariat_header: str = "") -> str:
    """The law's printed agency header. A bare "Office of the Secretary" (common in bond laws)
    says nothing on its own, so the secretariat header above it is used instead; a bare
    "Highway Division" gets its parent's name in front. Some offices are printed with only the
    ALL-CAPS heading ("JUDICIARY"), so that heading is used when there's no office line."""
    header = department_display_name(agency_header)
    if not secretariat_header:
        return header
    if not header or _VAGUE_HEADER.match(header):
        return department_display_name(secretariat_header)
    if _BARE_DIVISION.match(header):
        return f"{department_display_name(secretariat_header)} {header}"
    return header


class Departments:
    """CTHRU departments by display name and by line-item prefix (the first four digits)."""

    def __init__(self, cthru_rows: Iterable[Row]) -> None:
        self.prefixes: dict[str, set[str]] = defaultdict(set)  # department -> prefixes it uses
        by_prefix: dict[str, Counter] = defaultdict(Counter)  # prefix -> department counts
        for r in cthru_rows:
            name = department_display_name(r["department_name"])
            if name:
                self.prefixes[name].add(r["line_item"][:4])
                by_prefix[r["line_item"][:4]][name] += 1
        self.owner = {p: c.most_common(1)[0][0] for p, c in by_prefix.items()}

    def fix_inherited(self, agency: str, line_item: str) -> str:
        """A bond item with no heading of its own inherits the one above it, which can belong to
        another department (2022-140 §2: 7066-2011 under "The Department of Children and
        Families"). If the agency is a CTHRU department that never uses this line item's prefix,
        the prefix's own department is used instead."""
        prefix = line_item[:4]
        owner = self.owner.get(prefix)
        if owner and agency in self.prefixes and prefix not in self.prefixes[agency]:
            return owner
        return agency


def agency_office(
    row: Row,
    account: Row | None,
    secretariat_header: str = "",
    departments: Departments | None = None,
) -> str:
    """§8 column 9: the most specific administering office."""
    found = (
        agency_from_text(row["item_text"])
        or (account and agency_from_account(account["account_name"]))
        or (account and department_display_name(account["department_name"]))
    )
    if found:
        return found
    agency = header_agency(row["agency_header_raw"], secretariat_header)
    return departments.fix_inherited(agency, row["line_item"]) if departments else agency


def program_purpose(row: Row, account: Row | None) -> tuple[str, str]:
    """§8 column 10: ``(program_purpose, program_purpose_method)``."""
    if row["item_text"].strip():
        text = _drop_lead(first_clause(row["item_text"]))
    elif account and account["account_name"].strip():
        text = account["account_name"].strip()
        text = text.lower() if text.isupper() else text
    else:
        return "", ""
    text = text[:1].upper() + text[1:]
    if len(text) > 100:
        text = text[:100].rsplit(" ", 1)[0] + "…"
    return text, "rule"


# ---------------------------------------------------------------------------
# Policy area (§12)
# ---------------------------------------------------------------------------


def policy_area(
    line_item: str,
    fiscal_year: int,
    catalog: Mapping[str, Row],
    departments: Mapping[str, Row],
    cthru: Mapping[tuple[str, int], Row],
) -> tuple[str, str]:
    """Return ``(policy_area, policy_area_method)``. ``("", "")`` means the row needs review."""
    entry = catalog.get(line_item)
    if entry is not None:
        if entry["label_every_year"] == "true":
            return "", ""
        return entry["policy_area"], "catalog"
    account = cthru.get((line_item, fiscal_year))
    dept = departments.get(account["department_code"]) if account else None
    if dept and dept["mixed"] == "false" and dept["policy_area"]:
        return dept["policy_area"], "department"
    return "", ""


# ---------------------------------------------------------------------------
# Previously funded? and One-time or recurring (§8 columns 14-15)
# ---------------------------------------------------------------------------


def funded_years(
    cthru_rows: Iterable[Row], funding_rows: Iterable[Row]
) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
    """Return ``(funded, gaa_funded)``: sets of ``(line_item, fiscal_year)``.

    ``funded`` has any non-zero enacted authority that year, from CTHRU or the funding actions
    table. ``gaa_funded`` has non-zero authority in that year's GAA (original appropriation or
    retained-revenue ceiling).
    """
    funded: set[tuple[str, int]] = set()
    gaa: set[tuple[str, int]] = set()
    for r in cthru_rows:
        k = (r["line_item"], int(r["fiscal_year"]))
        if _int(r["original_enacted"]) or _int(r["retained_revenue_ceiling"]):
            gaa.add(k)
            funded.add(k)
        if _int(r["supplemental"]) or _int(r["total_enacted"]):
            funded.add(k)
    net: dict[tuple[str, int], int] = defaultdict(int)
    for r in funding_rows:
        if not r["line_item"] or r["funding_action"] not in AUTHORITY_ACTIONS:
            continue
        k = (r["line_item"], int(r["fiscal_year"]))
        net[k] += _int(r["amount"])
        if r["funding_action"] == "ORIG" and _int(r["amount"]):
            gaa.add(k)
    funded.update(k for k, amount in net.items() if amount)
    return funded, gaa


def previously_funded(line_item: str, fiscal_year: int, funded: set[tuple[str, int]]) -> str:
    """Q3: the year before only. A row with no line item can't be checked."""
    if not line_item:
        return "Unknown"
    return "Yes" if (line_item, fiscal_year - 1) in funded else "No"


def one_time_or_recurring(row: Row, gaa_funded: set[tuple[str, int]]) -> str:
    """Q3: recurring means in at least 2 consecutive GAAs, so first years count."""
    line_item, action = row["line_item"], row["funding_action"]
    if not line_item:
        return "Not classified"
    if action == "ORIG":
        fy = int(row["fiscal_year"])
        if (line_item, fy - 1) in gaa_funded or (line_item, fy + 1) in gaa_funded:
            return "Recurring"
        return "One-time"
    if action in ONE_TIME_ACTIONS:
        return "One-time"
    return "Not classified"


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def label_rows(
    funding_rows: list[Row],
    cthru_rows: list[Row],
    catalog_rows: Iterable[Row],
    department_rows: Iterable[Row],
    item_rows: Iterable[Row] = (),
) -> list[dict[str, str]]:
    """One labels.csv row per funding-action row, sorted by record_id.

    ``item_rows`` (items_raw and bond_items_raw) supply the secretariat header, which the
    funding actions table doesn't carry.
    """
    catalog = {r["line_item"]: r for r in catalog_rows}
    departments = {r["department_code"]: r for r in department_rows}
    cthru = {(r["line_item"], int(r["fiscal_year"])): r for r in cthru_rows}
    secretariats = {
        (r["law_key"], r["section"], r["line_item"]): r["secretariat_header_raw"] for r in item_rows
    }
    cthru_departments = Departments(cthru_rows)
    funded, gaa_funded = funded_years(cthru_rows, funding_rows)
    out = []
    for r in funding_rows:
        fy = int(r["fiscal_year"])
        account = cthru.get((r["line_item"], fy))
        secretariat = secretariats.get((r["law_key"], r["section"], r["line_item"]), "")
        purpose, purpose_method = program_purpose(r, account)
        area, method = policy_area(r["line_item"], fy, catalog, departments, cthru)
        label = dict.fromkeys(schemas.columns("labels"), "")
        label.update(
            record_id=r["record_id"],
            agency_office=agency_office(r, account, secretariat, cthru_departments),
            program_purpose=purpose,
            program_purpose_method=purpose_method,
            policy_area=area,
            policy_area_method=method,
            previously_funded=previously_funded(r["line_item"], fy, funded),
            one_time_or_recurring=one_time_or_recurring(r, gaa_funded),
            new_or_reapprop="Pending",
        )
        out.append(label)
    return sorted(out, key=lambda r: r["record_id"])


def write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.columns("labels"), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(ctx: Context) -> int:
    inputs = {
        "funding_actions": ctx.interim_dir / "funding_actions.csv",
        "cthru_line_items": ctx.interim_dir / "cthru_line_items.csv",
        "line_item_catalog": ctx.config_dir / "line_item_catalog.csv",
        "department_policy_areas": ctx.config_dir / "department_policy_areas.csv",
    }
    missing = [str(p) for p in inputs.values() if not p.exists()]
    if missing:
        print(f"  missing input: {', '.join(missing)}")
        return 1
    rows = {name: schemas.read_csv(path)[1] for name, path in inputs.items()}
    item_rows = []  # optional: only for secretariat headers
    for name in ("items_raw.csv", "bond_items_raw.csv"):
        if (ctx.interim_dir / name).exists():
            item_rows += schemas.read_csv(ctx.interim_dir / name)[1]
    labels = label_rows(
        rows["funding_actions"],
        rows["cthru_line_items"],
        rows["line_item_catalog"],
        rows["department_policy_areas"],
        item_rows,
    )
    write_labels(ctx.interim_dir / "labels.csv", labels)
    waiting = sum(1 for r in labels if not r["policy_area"])
    print(f"  labels: {len(labels)} rows; {waiting} waiting for a policy-area review")
    return 0
