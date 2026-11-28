# Codebook: Massachusetts appropriations, laws approved 2021–2025

This codebook explains the appropriations dataset built for the Office of the State Auditor: what
each file is, what every column means, allowable values, how the totals are counted, and known
limitations of the data. It's written for someone who reads budgets, not code. Where a rule was
decided by the Fall 2026 Capstone group’s community partner (a representative of the Office of the State
Auditor) or the student group, the decision is recorded in the Decision Log
([`DESIGN.md`](DESIGN.md) §20); this codebook records the rule, not the history.

*Draft of 27 Nov 2026. Examples are from the run of 27 Nov 2026 (CTHRU download of 13 Nov 2026).*

**Contents**
1. [Primary files](#1-primary-files)
2. [Calculating totals](#2-calculating-totals)
3. [Main file columns](#3-main-file-columns)
4. [Additional capital file columns](#4-additional-capital-file-columns)
5. [Summary file columns](#5-summary-file-columns)
6. [Values used in several columns](#6-values-used-in-several-columns)
7. [What counts toward totals](#7-what-counts-toward-totals)
8. [Known limitations](#8-known-limitations)
9. [Sources and validation](#9-sources-and-validation)

---

## 1. Primary files

| File | One row records |
|---|---|
| **Main file**, `ma_appropriations_cy2021_2025.csv` | One action a law took on one line item: an original appropriation in a budget, a supplemental increase, a reduction, a change of purpose, a transfer, money carried into the next year, and so on. A line item funded in five budgets has five rows. |
| **Capital file**, `ma_capital_authorizations_cy2021_2025.csv` | One item of a bond law: authority to borrow for a capital project. Same columns as the main file, plus 11 about the borrowing limit that covers the item. |
| **Summary file**, `ma_appropriations_summary_cy2021_2025.csv` | One total: the money counted for a fiscal year, overall or for one policy area or funding action. Made from the two files above, so it follows the same counting rules. |

**Which laws are in-scope:** Every law with an approval date falling between 1 Jan 2021 and
31 Dec 2025, inclusive, and which appropriates money or changes an appropriation: General
Appropriations Acts, supplemental budgets, surplus spending acts, bond acts, interim ("1/12th")
budgets, and other laws that change a budget item. Scope is decided by the **approval date**, not the
year on the law's volume: 2020 ch. 358 and ch. 383 were approved in January 2021, so they are
considered in-scope. The full list of laws, with a note on why each is in-scope, is
`config/law_list.csv`.

**Out of scope:**
- **Spending:** The dataset records what is authorized by law, not actual spending.
- **Earmarks as rows:** "Not less than $X shall be expended for…" is noted in its item's
  description, not as a row of its own.
- **Laws outside the window:** Some are read only to work figures out (for example the FY2021
  budget, approved in December 2020, for "Previously funded?" in FY2022); these reference-only laws
  have no rows.
- **Wording-only changes to bond items:** Not included in either file (Decision Log, 2026-11-11).

**On fiscal years:** A row's fiscal year is the year in which the money is authorized to be spent,
which isn't always the year the law was approved. A budget's items belong to its own year. A later
law that changes an item is recorded as the year of the budget it changes, so a few rows carry
fiscal years before 2021 (a 2024 law extending an item from 2019, for example). Bond items, and
items "available until" a later date, take the fiscal year that contains the approval date. The
state's fiscal year runs 1 July to 30 June: FY2024 is July 2023 to June 2024.

---

## 2. Calculating totals

**Add up "Amount counted toward total ($)", never "Appropriation/change ($)".** The latter column
shows every amount printed in the law, including money the counting rules leave out (federal grants,
chargebacks between agencies, money carried over from an earlier year, interim budgets, and
transfers). Adding these up would count some money twice and include federal money.

- To see only the rows that count towards totals, filter **"Counts toward total?"** to *Yes*.
- The **main file** records the **operating total**; the **capital file** records the separate
  **capital total** (borrowing authority). Never add the two together: borrowing authority is
  spent over many years and isn't part of any one year's budget.
- The **summary file** includes these totals already calculated, by fiscal year, policy area, and
  funding action. This file’s "All years" operating figure is equal to the main file's sum.
- Each run prints both totals, so an Excel figure can be checked against the run it came from.

---

## 3. Main file columns

The first 19 columns follow the initial framework developed by the student group, with
consultation and edits from OSA. "Veto status" and the two counting columns were added
after "Appropriation/change ($)".

The two examples used below are real rows:
- **A** = `2023-028-S2-0930-0100-ORIG-1`: a FY2024 budget line item for the Office of the Child
  Advocate.
- **B** = `2023-077-S178-2330-0100-INC-1`: a December 2023 supplemental budget line item raising
  the Division of Marine Fisheries' FY2024 item.

| # | Column | Definition | Values/example |
|---|---|---|---|
| 1 | **Record ID** | A permanent identifier for the row: the law's year and chapter, the section, the line item, the funding action, and a counter. A line item’s Record ID never changes between runs, so fixes and comments can refer to it. | A: `2023-028-S2-0930-0100-ORIG-1`. A row with no line item has `NOITEM`. |
| 2 | **Law citation** | The law, as cited in the Acts. | A: `2023 Acts, ch. 28` |
| 3 | **Law name** | A short descriptive name for the law, chosen by the student group. | A: `FY2024 General Appropriations Act` |
| 4 | **Enactment date** | The date the Governor signed the law, as month/day/year. (Every law in this period was signed; in future runs, the enactment date of a law passed over a veto would be the date of the override.) | A: `08/09/2023` |
| 5 | **Calendar year** | The year of the enactment date. | A: `2023` |
| 6 | **Fiscal year** | The fiscal year the money is for (see [§1](#1-primary-files), "On fiscal years"). | A: `2024`. B: `2024`, although the law is a FY2023 supplemental, because it changes the FY2024 budget. |
| 7 | **Section** | The section of the law that includes the line item: `2` for a budget's line items, `2A`, `2B`… for the other item sections, and a number for an "outside section". | A: `2`. B: `178` |
| 8 | **Line item** | The eight-digit appropriation account. Blank when the action has no line item (a transfer between funds, an interim budget). | A: `0930-0100` |
| 9 | **Agency / office** | The most specific office that runs the item: a division named in the item's text or the Comptroller's account name, otherwise the Comptroller's department for that year, otherwise the heading printed in the law (bond items). | A: `Office of the Child Advocate`. B: `Division of Marine Fisheries` (the law's heading says Department of Fish and Game). |
| 10 | **Program / purpose** | What the money is for, in a few words: the first clause of the item's description with "For the operation of…" removed, or the Comptroller's account name when the law has no description. A summary by rule, not a reading of the whole item. | A: `Office of the child advocate` |
| 11 | **Policy area** | One of 18 policy areas (see [§6](#policy-area)). Set once per line item, by a person or by the item's department, and applied in every year. | A: `Children and families` |
| 12 | **Funding action** | What the law does with the line item (see [§6](#funding-action)). | A: `Original appropriation`. B: `Supplemental increase` |
| 13 | **Appropriation/change ($)** | The amount the law gives or changes, in dollars with thousands separators; negative for a reduction. For a budget item, the Comptroller's enacted amount, which already reflects vetoes and overrides; for everything else, the law's printed amount. Blank when the action has no amount (a change of purpose, an extension of an end date). **Don't add this column up** ([§2](#2-calculating-totals)). | A: `6,077,671`. B: `350,000` |
| 13a | **Veto status** | Whether the item was vetoed, and if so, how (see [§6](#veto-status)). | A: `none` |
| 13b | **Counts toward total?** | `Yes` if the row's money counts toward the file's total under the dataset’s counting rules ([§7](#7-what-counts-toward-totals)); otherwise `No`. In the capital file every bond item is `Yes`, because it counts toward the separate capital total. | A: `Yes` |
| 13c | **Amount counted toward total ($)** | All dollars that count towards total: the amount less any federal share; `0` for a `No` row; blank when the row has no amount. **This is the column to add up.** | A: `6,077,671` |
| 14 | **Previously funded?** | Whether the same line item had money in the previous fiscal year (in the Comptroller's data or in our rows). An item funded two years earlier but not last year is `No`. | `Yes`, `No`, or `Unknown` when the row has no line item to check. A: `Yes` (the item had money in FY2023). |
| 15 | **One-time or recurring funding** | For a budget item: `Recurring` if the line item is also in the budget the year before **or** the year after (so a program's first year is recurring when the next budget funds it again), otherwise `One-time`. Supplemental, surplus, and bond money is `One-time`. | `Recurring`, `One-time`, or `Not classified` for actions that move or extend existing money (transfers, changes of purpose, carried-over money, and reauthorizations), interim budgets, and rows with no line item. A: `Recurring`. B: `One-time` |
| 16 | **New funding appropriation or re-appropriation of existing funding?** | Whether the law gives new money. | `New` (appropriations, supplemental increases and reductions, bond items, and interim budgets, which give new authority even though they never count toward a total); `Re-appropriation` (money carried into the next year and reauthorizations); `Transfer of existing authority` (transfers and changes of purpose). A: `New` |
| 17 | **Human review status** | `Human reviewed` if a person corrected the row, checked it against the law and confirmed it (the random review of rows), or decided its line item's policy area; otherwise `Not human reviewed`. A row marked only because of its policy area hasn't necessarily had its amount checked by a person. A `Not human reviewed` row was made by the program's rules, which were checked on samples and on a random review of rows ([§9](#9-sources-and-validation)). | `Human reviewed`, `Not human reviewed` |
| 18 | **Source URL** | Where to find the law on the Legislature's website. | A: `https://malegislature.gov/Laws/SessionLaws/Acts/2023/Chapter28` |
| 19 | **Source or calculation for total** | A note about the **law as a whole**, not the individual line item: how many of its rows have an amount, the new money it counts, how many of its items were compared with the Comptroller's figures and match exactly, and the gap for those that don't. It starts `Total checked`, `Total partly checked`, or `Total not checked against CTHRU`. It states only what was checked, with no tolerance: a $1 difference is reported. For bond laws it says whether the borrowing limits match their items. | A (start): `Total partly checked: 1,423 rows with an amount, net new $…; 843 of 846 items compared match CTHRU FY2024; …` |

**`Unknown`, `Not classified`, and `Pending`** (the partner's definitions, 6 Nov): `Unknown` means a
fact couldn't be established; `Not classified` means no category applies or none was assigned;
`Pending` means a decision is still open. They're used only in those cases; as of this run, no
column uses `Pending`.

---

## 4. Additional capital file columns

The capital file has the 22 columns described in the previous section (its "Appropriation/change
($)" is the item's full project amount), then the below 11. Each describes the **borrowing limit**
that covers the item: the section of the bond law that lets the Treasurer borrow up to a set amount
for a group of items, and on what terms. Items under the same limit repeat the same values.

| Column | Definition |
|---|---|
| **Borrowing limit section** | The section of the bond law that sets the limit (e.g. `96`). Blank if no limit covers the item. |
| **Borrowing limit ($)** | The most the Treasurer may borrow under that section. |
| **Total of items under this limit ($)** | The total of the items the limit covers. Often equal to the limit; when not, see "Limit difference note". |
| **Identified federal share ($)** | The part of the items' cost the law itself says federal money will pay. Left out of the capital total. Blank when the law identifies none. |
| **Federal split** | `Identified` (the law states the federal share), `Unknown` (the items may get federal money but the law doesn't say how much, so the full amount stays in the total), or `None` (no federal money mentioned). Blank if no limit covers the item. |
| **Limit difference note** | When the items don't add up to the limit, which limit and how big the gap is, e.g. "covered by §4: items exceed the borrowing limit by $400,000,000". The causes found are identified federal shares, vetoes after the limit was set, and two gaps the laws don't explain ([§8](#8-known-limitations)). |
| **Bond name** | The name the law gives the bonds (e.g. `Commonwealth Economic Development Act of 2021`). |
| **Maximum term (years)** | The longest length of time allowed between issue date and final repayment. |
| **Final payable date** | The date by which the bonds must be repaid, as month/day/year. |
| **Fund paying the bonds** | The fund the law says repays the bonds (e.g. `General Fund`). Blank when the law doesn't name one; the program does not assume the General Fund. |
| **Spending authority through** | The date until which the money may be spent, when the law sets one. |

---

## 5. Summary file columns

| Column | Definition |
|---|---|
| **Breakdown** | Which kind of total the row is: `Operating total`, `Operating, by policy area`, or `Operating, by funding action` (from the main file); `Capital total` or `Capital, by policy area` (from the capital file). |
| **Fiscal year** | The fiscal year, or `All years` for the total across them. |
| **Group** | The policy area or funding action the row totals; `All` for the overall totals. |
| **Rows counted** | How many rows of the main or capital file the total adds up (only rows whose "Counts toward total?" is `Yes`). |
| **Amount counted toward total ($)** | The sum of those rows' "Amount counted toward total ($)". |

---

## 6. Values used in several columns

### Funding action
| Value | What the law does with the line item | Counts toward the total? |
|---|---|---|
| Original appropriation | An item of an annual budget | Yes, unless it's federal money or a chargeback ([§7](#7-what-counts-toward-totals)) |
| Supplemental appropriation | A new item in a supplemental budget | Yes |
| Supplemental increase | Raises an existing item | Yes |
| Supplemental reduction | Lowers an existing item | Yes, as a negative amount |
| Interim appropriation | An interim ("1/12th") budget: funds the government until the annual budget passes | No: by law, interim appropriations are charged against the budget that follows |
| Capital authorization | An item of a bond law | Toward the separate capital total only (capital file) |
| Reauthorization | Extends the time by which an earlier appropriation may be spent | No: not new money |
| Prior appropriation continued | Carries an unspent balance into the next year | No: not new money |
| Alteration of purpose | Changes what an item may be spent on, not its amount | No |
| Transfer | Moves money between items or funds | No (see [§7](#7-what-counts-toward-totals) for transfers out of a reserve into an item) |

Two more values are allowed but not used in this iteration of the dataset: *Veto reduction* and
*Veto override restoration*. Vetoes are netted into the item's own row instead (see "Veto status").

### Veto status
The file shows these as short codes.

| Value | Meaning |
|---|---|
| `none` | No veto. |
| `vetoed` | The Governor vetoed the whole item; its amount is $0. |
| `reduced` | The Governor reduced the item; the row shows the reduced amount. |
| `overridden` | The Governor vetoed or reduced the item and the Legislature overrode the veto; the row shows the restored amount. |
| `partial_override` | The Legislature restored only part of a cut. Allowed but never used: the laws don't print the figure before the cut, so a partial override can't be told from a full one ([§8](#8-known-limitations)). |
| `wording_vetoed` | The Governor struck some of the item's wording but not its amount. The description shows the wording as finally enacted. |
| `unknown` | Can't be checked. All federal grant items (budget section 2D) are `unknown`, because the Comptroller's data doesn't list them. |

### Policy area
The dataset classifies line items into one of 18 policy areas. These policy areas, and what they
cover, were decided by OSA. Where a department's work falls within one policy area, its line items
take that area by default, though this changed in some instances after human review. Items in
departments with mixed missions were classified one by one, according to the purpose of the line
item itself.

- Education: Early education and child care, K–12 schools, higher education, student aid, and school construction.
- Health and public health: MassHealth, hospitals, public health, mental health, substance use treatment, and disease prevention.
- Children and families: Child protection, foster care, adoption, family support, and child advocacy.
- Human services and income support: Cash and food assistance, disability services, aging services, and support for independent living.
- Housing and homelessness: Affordable housing, rental assistance, shelters, homelessness prevention, and housing development.
- Economic development and workforce: Business assistance, job training, employment services, unemployment programs, tourism promotion, and economic development projects.
- Transportation: Roads, bridges, public transit, rail, airports, ports, and pedestrian and bicycle infrastructure.
- Environment and natural resources: Conservation, water and sewer infrastructure, environmental protection, agriculture, fisheries, energy, and climate programs.
- Public safety and corrections: Police, fire services, emergency management, prisons, sheriffs, and correctional programs.
- Courts and legal services: Courts, prosecution, public defense, civil legal aid, and legal assistance for victims.
- Veterans’ services: Veterans’ benefits, services, housing, and veterans’ homes. (The name has a curly apostrophe.)
- Arts, culture, and recreation: Libraries, museums, arts programs, historic preservation, parks, and recreation facilities.
- Government administration and oversight: Legislative and executive operations, elections, tax administration, auditing, general regulation, and shared facilities and technology.
- General local aid: Unrestricted aid to municipalities and other local assistance without a specified policy purpose.
- Public employee pensions and benefits: Pension contributions, employee and retiree health insurance, and other centrally funded employee benefits.
- Debt service, reserves, and statewide finance: Debt payments, general contingency reserves, stabilization funds, and transfers without a specified policy purpose.
- Multiple: Funding covers several policy areas with no clear primary purpose.
- Unclassified/other: The purpose is unclear, has not yet been reviewed, or does not fit the categories above. Explain the reason in the project research log.

The program decides policy area based on the following information, in order:
1. the line item's row in the catalog (`config/line_item_catalog.csv`), decided by a person or
   filled in from the department;
2. otherwise the area of the item's department (`config/department_policy_areas.csv`);
3. rows with no line item take an area by rule: transfers between funds are *Debt service,
   reserves, and statewide finance*, and interim budgets are *Multiple*.

Reserve items (numbers starting 1599) are decided each year by a person, because the same number is
reused for different purposes.

---

## 7. What counts toward totals

The operating total is meant to measure **new appropriation authority**: each dollar of new state
money counted once.

| Counted | Not counted |
|---|---|
| Items of the annual budgets (sections 2 and 2F), including fee-funded items, which count at the amount the law lets the agency spend | Chargebacks (section 2B): one agency paying another for a service. The money is already counted in the paying agency's item |
| New items and increases in supplemental budgets | Federal grants (section 2D) and the federal share of any item: kept in the file, flagged, and left out of the total. State surplus money counts as state money |
| Reductions, as negative amounts | Transfers into trust funds: the money counts when it's appropriated out of the trust instead |
| Money moved from a reserve or escrow fund into a line item: counted once, at the item | Transfers into reserve or escrow funds, and transfers between items or funds |
| | Interim budgets (charged against the budget that follows) |
| | Money carried into the next year, reauthorizations, and changes of purpose (not new money) |

**Bond items:** Bond items count only toward the separate **capital total**. The capital total is
the items' full amounts, less any federal share the law identifies. When the law says that federal
money may come in but does not specify an amount, the full amount is counted in the total. A later
law that restates an earlier bond item counts only a change in its amount. Pocket-vetoed items are
left out.

---

## 8. Known limitations

This section details information that the dataset cannot specify, instances that are out of scope,
or where the dataset differs from another source for a reason we know. Each known limitation was
investigated by the student group; the Decision Log and `review/research_log.md` provide the details
of that review process.

**Window and scope:**
- **Laws approved after 31 Dec 2025 are out of scope.** For FY2026, the Comptroller already shows
  supplemental money from 2026 laws, which the dataset does not include.
- **No actual spending numbers.** The figures are what the laws authorize; they do not reflect what
  was spent, or the Governor's mid-year "9C" cuts (FY2024 only in this period), which the
  Comptroller records separately.

**Vetoes:**
- **Partial overrides show as `overridden`.** The laws print only the Governor's reduced figure, not
  the one before the cut, so a partial restoration can't be told from a full one. The amount itself
  is right (derived from Comptroller data).
- **Federal grant items and bond items rely on the law's own veto notes.** The Comptroller's data
  doesn't cover them, so a veto the law text doesn't mark cannot be checked.

**Differences from the Comptroller (CTHRU) for identified reasons:**
- Where a law and the Comptroller differ, the dataset keeps the law's figure (for anything but a
  budget item) and the "Source or calculation for total" column reports the difference. Most
  differences have been explained one by one; the explanations are in
  `review/queue_explanations.csv`.
- Four items where the Comptroller's ceiling differs from the law's and no law in our list explains
  it: 7003-0201 and 8100-0018 (FY2022), 3000-7040 (FY2024), and 7006-0011 (FY2025).
- **Increases the Comptroller data does not show:** a few outside-section increases in FY2024 laws
  signed without vetoes (4512-0205, 8324-0050, and 1599-0026), and 2024 ch. 248's $25,000 cut to
  7006-0071, approved after FY2024 closed.

**Bonds:**
- **Two borrowing limits are smaller than their items, and the laws don't specify why:** 2022 ch. 176
  §48 and 2024 ch. 139 §4. Possible explanations include federal reimbursement or items meant to
  overlap. Their federal split is `Unknown`, so the full item amounts are included in the capital
  total.
- **2024 ch. 139 (FutureTech Act) names no fund to repay its bonds,** so "Fund paying the bonds" is
  blank for its 12 items.

**Misprints in the laws:**
- **FY2025's item 3000-4060** prints fund shares of 80.49% and 19.41%, which add up to 99.90%. The
  Comptroller data books the item to the General Fund only, so the dataset cannot say which figure
  is wrong. No amount or total depends on this.

**Checks not built:**
- Two consistency checks weren't built, because nothing in the data or the random review suggested a
  problem: that an item's number matches its department in the Comptroller's data, and that no item
  appears twice in one section.

---

## 9. Sources and validation

**Sources:**
- **Session laws**, from the Legislature's website: the text of each law, read by the program.
- **CTHRU**, the Comptroller's statewide budget data: the enacted amount of every budget item, which
  already reflects vetoes and overrides. The download used is saved with its date
  (`data/raw/cthru/`).

**Methodology:** The student group built a program that downloads each law from the Legislature's
website and the Comptroller's budget data, reads them, and builds the rows by fixed rules. The student group, with frequent consultation from OSA, decided the policy
areas, the counting rules, and every case the rules didn't settle; each decision is in the Decision
Log. One-off fixes are recorded in `review/corrections.csv` and applied on every subsequent run. Two
rows the program can't build are kept by hand, with a quote from the law
(`config/manual_rows.csv`).

**Validation and checks:**
- **Against the Comptroller:** every budget item, supplemental change, and fee-funded item that
  CTHRU covers is compared with CTHRU's figure, with no tolerance. Each law's result is in its
  "Source or calculation for total" note.
- **Bond items against their borrowing limits:** the result is in the capital file's "Limit
  difference note".
- **A random review of rows against law text,** with findings applied to the dataset and, where
  appropriate, edits made to the program, to improve its functionality with every run.
- **Automatic checks on every run:** that every law in the window has rows, every correction
  reaches the file, every budget item has a description, and the fund shares add up.
- **A review queue** (`review/review_queue.csv`) lists every row that still needs a person, with
  the reason.

**Which run a file comes from:** Each published copy of the files goes on a GitHub release. The
notes on each GitHub release name the version of the program that made it. The program's message at
the end of each run gives the row counts and both totals, so a copy can be matched to its run.
