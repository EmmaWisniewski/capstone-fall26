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
  via the line's CTHRU department (that fiscal year, else another year, else the department
  that owns the line's first four digits, which covers bond items CTHRU doesn't list), else
  empty, which sends the row to the review queue. Rows with no line item get an area by rule
  (decided by D, 2026-11-11): fund transfers are *Debt service, reserves, and statewide
  finance* and interim budgets are *Multiple*.
- Previously funded? (§8 column 14, Q3): ``Yes`` if the line had non-zero enacted authority in
  the fiscal year before the row's, else ``No``.
- One-time or recurring (§8 column 15, Q3): a GAA row is ``Recurring`` if the line was also in
  the GAA the year before or the year after, else ``One-time``. Supplemental and bond rows are
  ``One-time`` (interim rule).
- New vs. re-appropriation (§8 column 16, Q3 decided by the group 2026-11-11): appropriations,
  supplemental increases and reductions, and bonds are ``New``; carried-over money and
  reauthorizations are ``Re-appropriation``; transfers and purpose changes are ``Transfer of
  existing authority``; interim budgets stay ``Pending``.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from ma_approps import schemas
from ma_approps.context import Context

IMPLEMENTED = True

# Files label reads, and the stage that writes each (§6). Missing ones are reported, not fatal,
# like combine: the rows that need them get fewer labels.
INPUTS = {
    "funding_actions": ("interim", "funding_actions.csv", "combine"),
    "cthru_line_items": ("interim", "cthru_line_items.csv", "cthru"),
    "items_raw": ("interim", "items_raw.csv", "read_items"),
    "bond_items_raw": ("interim", "bond_items_raw.csv", "read_bonds"),
    "line_item_catalog": ("config", "line_item_catalog.csv", None),
    "department_policy_areas": ("config", "department_policy_areas.csv", None),
}

# Funding actions that add or remove enacted authority (§9.2). Reauthorizations, transfers,
# purpose changes and interim budgets don't fund a line on their own.
AUTHORITY_ACTIONS = frozenset(("ORIG", "NEW", "INC", "RED", "VETO", "OVR", "CAP"))
ONE_TIME_ACTIONS = frozenset(("NEW", "INC", "RED", "CAP"))
REAPPROPRIATION_ACTIONS = frozenset(("REAUTH", "PAC"))
TRANSFER_ACTIONS = frozenset(("XFER", "PURP"))
# Policy area for rows with no line item, by funding action (D, 2026-11-11): a transfer
# between funds, or a stopgap budget that covers the whole government
NO_LINE_ITEM_AREAS = {
    "XFER": "Debt service, reserves, and statewide finance",
    "INT": "Multiple",
}

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
    text = re.sub(r"^v(?=For\b)", "", text)  # a stray "v" after the item number (2024-140)
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


def name_key(name: str) -> str:
    """A loose key for matching department names between the laws and CTHRU: "Department of
    Elementary and Secondary Education" = "DEPARTMENT OF ELEMENTARY & SECONDARY EDUCATION",
    "Massachusetts Emergency Management Agency" = "EMERGENCY MANAGEMENT AGENCY"."""
    key = re.sub(r"^the\s+", "", name.lower().replace("&", " and "))
    key = re.sub(r"\bmassachusetts\s+", "", key)
    return " ".join(re.sub(r"[^a-z ]", " ", key).split())


class Departments:
    """CTHRU departments by display name and by line-item prefix (the first four digits)."""

    def __init__(self, cthru_rows: Iterable[Row]) -> None:
        self.prefixes: dict[str, set[str]] = defaultdict(set)  # department -> prefixes it uses
        by_prefix: dict[str, Counter] = defaultdict(Counter)  # prefix -> department counts
        codes_by_prefix: dict[str, Counter] = defaultdict(Counter)  # prefix -> department codes
        self.line_codes: dict[str, dict[int, str]] = defaultdict(dict)  # line -> {year: code}
        self.line_names: dict[str, dict[int, str]] = defaultdict(dict)  # line -> {year: name}
        self.name_code: dict[str, str] = {}  # name_key(display name) -> department code
        for r in cthru_rows:
            name = department_display_name(r["department_name"])
            if name:
                self.prefixes[name].add(r["line_item"][:4])
                by_prefix[r["line_item"][:4]][name] += 1
                self.line_names[r["line_item"]][int(r["fiscal_year"])] = name
            if r["department_code"]:
                self.line_codes[r["line_item"]][int(r["fiscal_year"])] = r["department_code"]
                codes_by_prefix[r["line_item"][:4]][r["department_code"]] += 1
                if name:
                    self.name_code.setdefault(name_key(name), r["department_code"])
        self.owner = {p: c.most_common(1)[0][0] for p, c in by_prefix.items()}
        self.owner_code = {p: c.most_common(1)[0][0] for p, c in codes_by_prefix.items()}

    def department_code(self, line_item: str, fiscal_year: int, names: Iterable[str] = ()) -> str:
        """The line's CTHRU department that year, else in its latest year, else the department
        that owns its first four digits, else a department whose name was printed in the law
        (MassDOT's capital lines, for example, never appear in CTHRU)."""
        years = self.line_codes.get(line_item)
        if years:
            return years.get(fiscal_year) or years[max(years)]
        if line_item[:4] in self.owner_code:
            return self.owner_code[line_item[:4]]
        keys = [name_key(n) for n in names if n]
        return next((self.name_code[k] for k in keys if k in self.name_code), "")

    def name_for(self, line_item: str, fiscal_year: int) -> str:
        """The line's CTHRU department name that year, else in its latest year, else the name of
        the department that owns its first four digits."""
        years = self.line_names.get(line_item)
        if years:
            return years.get(fiscal_year) or years[max(years)]
        return self.owner.get(line_item[:4], "")

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
    if not departments:
        return agency
    if agency:
        return departments.fix_inherited(agency, row["line_item"])
    # An amendment's own text names no office: the line's department in CTHRU
    if not row["line_item"]:
        return ""
    return departments.name_for(row["line_item"], int(row["fiscal_year"]))


def is_legal_text(text: str) -> bool:
    """An amending section's wording ("SECTION 178. Said item 2330-0100 … is hereby amended …")
    rather than a description of what the line pays for."""
    return bool(re.match(r"\s*(?:section\s+\d|said\s+item|item\s+\d{4}-\d{4})", text, re.I))


def program_purpose(row: Row, account: Row | None, known: str = "") -> tuple[str, str]:
    """§8 column 10: ``(program_purpose, program_purpose_method)``.

    For an amendment row, whose text is the amending section, ``known`` is the line's own
    purpose from its other rows; the CTHRU account name comes next.
    """
    if row["item_text"].strip() and not is_legal_text(row["item_text"]):
        text = _drop_lead(first_clause(row["item_text"]))
    elif known:
        return known, "rule"
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
    cthru_departments: Departments | None = None,
    printed_names: Iterable[str] = (),
) -> tuple[str, str]:
    """Return ``(policy_area, policy_area_method)``. ``("", "")`` means the row needs review.

    ``printed_names`` are department names from the law (secretariat header, agency), used only
    when CTHRU has no department for the line or its first four digits.
    """
    entry = catalog.get(line_item)
    if entry is not None:
        if entry["label_every_year"] == "true":
            return "", ""
        return entry["policy_area"], "catalog"
    account = cthru.get((line_item, fiscal_year))
    if account:
        code = account["department_code"]
    elif cthru_departments:
        code = cthru_departments.department_code(line_item, fiscal_year, printed_names)
    else:
        code = ""
    dept = departments.get(code)
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


def new_or_reapprop(row: Row) -> str:
    """Q3 (group, 2026-11-11): the §8 column 16 rule, by funding action."""
    action = row["funding_action"]
    if action in AUTHORITY_ACTIONS:
        return "New"
    if action in REAPPROPRIATION_ACTIONS:
        return "Re-appropriation"
    if action in TRANSFER_ACTIONS:
        return "Transfer of existing authority"
    return "Pending"  # interim budgets: no rule decided


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
    latest_account = {r["line_item"]: r for r in sorted(cthru_rows, key=lambda r: r["fiscal_year"])}
    funded, gaa_funded = funded_years(cthru_rows, funding_rows)
    def agency_for(r: Row) -> str:
        account = cthru.get((r["line_item"], int(r["fiscal_year"])))
        secretariat = secretariats.get((r["law_key"], r["section"], r["line_item"]), "")
        return agency_office(r, account, secretariat, cthru_departments)

    # Each line's own agency and purpose, from rows whose text describes it, so an amendment
    # row (whose text is the amending section) matches the line it changes
    known: dict[tuple[str, int], tuple[str, str]] = {}
    for r in sorted(funding_rows, key=lambda r: r["funding_action"] != "ORIG"):
        if r["line_item"] and r["item_text"].strip() and not is_legal_text(r["item_text"]):
            key = (r["line_item"], int(r["fiscal_year"]))
            if key not in known:
                known[key] = (agency_for(r), program_purpose(r, None)[0])
    by_line: dict[str, tuple[str, str]] = {}
    for (line, _fy), pair in sorted(known.items(), key=lambda kv: -kv[0][1]):
        by_line.setdefault(line, pair)  # latest year first
    out = []
    for r in funding_rows:
        fy = int(r["fiscal_year"])
        account = cthru.get((r["line_item"], fy))
        secretariat = secretariats.get((r["law_key"], r["section"], r["line_item"]), "")
        known_agency, known_purpose = ("", "")
        if is_legal_text(r["item_text"]) or not r["item_text"].strip():
            known_agency, known_purpose = known.get((r["line_item"], fy)) or by_line.get(
                r["line_item"], ("", "")
            )
        agency = known_agency or agency_for(r)
        purpose, purpose_method = program_purpose(
            r, account or latest_account.get(r["line_item"]), known_purpose
        )
        printed = (agency, department_display_name(secretariat))  # the narrower name first
        if not r["line_item"] and r["funding_action"] in NO_LINE_ITEM_AREAS:
            area, method = NO_LINE_ITEM_AREAS[r["funding_action"]], "rule"
        else:
            area, method = policy_area(
                r["line_item"], fy, catalog, departments, cthru, cthru_departments, printed
            )
        label = dict.fromkeys(schemas.columns("labels"), "")
        label.update(
            record_id=r["record_id"],
            agency_office=agency,
            program_purpose=purpose,
            program_purpose_method=purpose_method,
            policy_area=area,
            policy_area_method=method,
            previously_funded=previously_funded(r["line_item"], fy, funded),
            one_time_or_recurring=one_time_or_recurring(r, gaa_funded),
            new_or_reapprop=new_or_reapprop(r),
        )
        out.append(label)
    bond_change_areas(funding_rows, out)
    return sorted(out, key=lambda r: r["record_id"])


def bond_change_areas(funding_rows: list[Row], labels: list[dict[str, str]]) -> None:
    """A later law's change to a bond item (a ``CAP`` row whose ``target_law_key`` is another
    law, e.g. 2021-25 §3 raising 2020-383 item 6121-2118) with no policy area of its own takes
    the policy area of the item it changes, the way it takes that item's agency. MassDOT's
    capital lines aren't in CTHRU, so the department lookup often finds nothing for them."""
    by_id = {r["record_id"]: r for r in funding_rows}
    original = {
        (r["law_key"], r["line_item"]): label
        for label in labels
        if (r := by_id[label["record_id"]])["funding_action"] == "CAP"
        and r["law_key"] == r["target_law_key"]
        and label["policy_area"]
    }
    for label in labels:
        r = by_id[label["record_id"]]
        if label["policy_area"] or r["funding_action"] != "CAP":
            continue
        if not r["target_law_key"] or r["target_law_key"] == r["law_key"]:
            continue
        item = original.get((r["target_law_key"], r["line_item"]))
        if item:
            label["policy_area"] = item["policy_area"]
            label["policy_area_method"] = item["policy_area_method"]


def write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schemas.columns("labels"), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(ctx: Context) -> int:
    dirs = {"config": ctx.config_dir, "interim": ctx.interim_dir}
    rows: dict[str, list[dict[str, str]]] = {}
    for name, (where, filename, stage) in INPUTS.items():
        path = dirs[where] / filename
        if path.exists():
            rows[name] = schemas.read_csv(path)[1]
        else:
            rows[name] = []
            hint = f" (run the {stage} stage first)" if stage else ""
            print(f"  WARNING: {filename} is missing{hint}: rows that need it get fewer labels")
    labels = label_rows(
        rows["funding_actions"],
        rows["cthru_line_items"],
        rows["line_item_catalog"],
        rows["department_policy_areas"],
        rows["items_raw"] + rows["bond_items_raw"],
    )
    path = ctx.interim_dir / "labels.csv"
    write_labels(path, labels)
    bad = len(schemas.validate_file("labels", path))
    waiting = sum(1 for r in labels if not r["policy_area"])
    print(f"  labels: {len(labels)} rows; {waiting} waiting for a policy-area review; "
          f"format problems: {bad}")
    return 1 if bad else 0
