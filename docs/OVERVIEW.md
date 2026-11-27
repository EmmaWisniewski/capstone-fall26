# Project overview (start here)

A plain-language tour of what this project builds, how the program works, and what's left to do
before the final deliverables on 11 December. It is deliberately short. For the full detail, see
[`DESIGN.md`](DESIGN.md), which is the source of truth whenever the two disagree.

New to git or Claude Code? Read [`WORKFLOW.md`](WORKFLOW.md) next.

---

## 1. What we're building

We're building a spreadsheet (a CSV file) with **one row for every Massachusetts state
appropriation in a law approved between January 1, 2021 and December 31, 2025**. An appropriation is
money the Legislature legally authorizes the state to spend. Each row says which law did it, which
budget line item, which agency, how many dollars, and which of 18 policy areas it belongs to.
The target format is [`exampledata.csv`](../exampledata.csv).

**One example row, in words (EX-004):** The *FY2023 Supplemental Appropriations Act* (2023 Acts,
ch. 77, signed 12/04/2023) has a Section 178 that changes line item **2330-0100** (Division of
Marine Fisheries) from $9,310,231 to $9,660,231. That is a **Supplemental increase of
$350,000**, and it counts toward **fiscal year 2024** because the item it changes belongs to the
FY2024 budget.

**Just as important: a program someone else can re-run every year.** Next year an analyst at the
State Auditor's office will add the 2026 laws. They aren't a programmer and won't have Claude
Code: they'll download a copy of this repository and follow the [runbook](RUNBOOK.md). So the
program has to be automatic, sturdy, and need as few steps and commands as possible.

---

## 2. The big picture: two sources, then combining

The program combines two sources:

- **The Comptroller's CTHRU data**, a clean, official, structured dataset. For every line item in
  every year's annual budget, it gives the final amount (after vetoes), the agency, and history
  back to 2005. **Wherever CTHRU has what we need, we use it.** Structured data is much less
  fragile than reading web pages.
- **The text of the laws** from the Legislature's website. We read it only for what CTHRU doesn't
  have:
  - *which* supplemental budget changed an item, and when;
  - bond (borrowing) laws;
  - sections that amend earlier laws;
  - each item's description.

```mermaid
flowchart LR
  CT["Comptroller CTHRU data<br/>annual budgets, agencies"] --> P
  L["Law list + downloads"] --> R1["Read supplemental budgets"]
  L --> R2["Read bond laws"]
  L --> R3["Read amendments"]
  R1 --> P["Put it together"]
  R2 --> P
  R3 --> P
  P --> LB["Add labels"]
  LB --> X["Final dataset + checks"]
```

---

## 3. The moving parts

Each stage is **one Python file** in `src/ma_approps/`. You run them all with
`python -m ma_approps run --stage all`, or one at a time with `--stage cthru` and so on.

| # | Stage (file) | Its job, in plain words |
|---|---|---|
| 1 | `laws.py` | Finds each year's spending laws for humans to approve, and downloads their text (slowly and politely, saving a copy) |
| 2 | `cthru.py` | Downloads the Comptroller's budget data, saves a dated copy, and lists every line item per year with its amount and agency |
| 3 | `read_items.py` | Reads line items in supplemental budgets, and item descriptions in annual budgets |
| 4 | `read_bonds.py` | Reads the items in bond (borrowing) laws, including Chapter 90 road money |
| 5 | `read_amendments.py` | Reads sections that change earlier items ("strike out $9,310,231, insert $9,660,231") and lump-sum interim budgets |
| 6 | `combine.py` | Combines everything into one master table, the **funding actions table** (one row per legal action on an item), gives each row its ID, and decides whether it counts toward totals |
| 7 | `label.py` | Fills in agency, program purpose, policy area, and "previously funded?" |
| 8 | `export.py` | Applies human corrections and writes the final CSV in exactly the `exampledata.csv` format |
| — | `validate.py` | Runs the checks: our numbers vs. CTHRU, nothing left unread, IDs unique |
| shared | `paragraphs.py` | Turns a law's web-page code into clean, numbered paragraphs; used by all three law readers (stages 3–5) |
| shared | `schemas.py` | The single list of every column name and allowed value that the stages pass between each other |

---

## 4. Where things live

```
README.md, CLAUDE.md          setup steps; rules Claude follows in this repo
docs/                         OVERVIEW (this), WORKFLOW (git + Claude), DESIGN (full detail),
                              RUNBOOK and CODEBOOK (for the analyst; CODEBOOK still to write)
exampledata.csv               the target format (4 example rows)
policyareas.csv               the 18 allowed policy areas
config/                       files humans edit: the law list, the label spreadsheets, fix files, settings
src/ma_approps/               THE PROGRAM: one .py file per stage
tests/                        automatic checks, plus saved copies of sample laws (samples)
review/                       one-off human fixes (corrections.csv) and reasoning (research_log.md)
data/raw/                     downloaded laws and CTHRU copies (your computer only, never committed)
data/interim/, data/output/   files the program generates (never edit by hand; git ignores them,
                              and the final files go on a GitHub release)
reports/                      check results the program generates (never edit by hand; git ignores
                              them, and the final run's go on the release)
```

---

## 5. Finishing plan

### Deliverables

| Deliverable | For | What it is |
|---|---|---|
| **The dataset** | our partner | The main spreadsheet and the separate bond (capital) spreadsheet, emailed to the partner, and also attached to a GitHub release (a fixed, downloadable version) |
| **The runbook** ([`RUNBOOK.md`](RUNBOOK.md)) | the analyst | Step-by-step instructions for adding a new year of laws, without Claude Code |
| **The codebook** (`CODEBOOK.md`, to write) | the analyst and our partner | Every column, allowed value and counting rule in plain words, plus the known limitations |

### Deadlines

**Until 4 December, checking the data and edge cases come first.** Re-run and documentation work
waits unless it's tiny or helps the checking. After 4 December, the re-run, runbook and codebook
come first.

**Fri 4 Dec: the data is reliable.** The students present simple Excel bar graphs of it that day.
Done when:
- ☐ the random-row review is done and its findings are applied;
- ☐ the review queue is built and its high-priority rows are worked;
- ☐ every open question in [DESIGN §19](DESIGN.md#19-open-questions), plus the 8 borrowing-limit
  differences and issue #36, is fixed or recorded as a known limitation;
- ☐ recurring edge cases found in review are handled in code;
- ☐ the main file is safe to total in Excel, and the copy used for the presentation records which
  run it came from.

**Fri 11 Dec: final.** Done when:
- ☐ the runbook is rewritten for the analyst and followed on the 2026 laws, without Claude Code, by
  someone who didn't write the program;
- ☐ the yearly hand edits are gone;
- ☐ the spreadsheet's ease-of-use fixes are in;
- ☐ the codebook is final;
- ☐ the final files are emailed to the partner and published on a GitHub release.

*Nice to have, not required:* the extended file (the main file plus every column the program keeps
internally), unless the partner asks for it.

### Task list

**Edit only your own row**, so you don't get merge conflicts. **Who's on it** is filled in by
whoever picks a task up, and pushed to `main` straight away (`/start-task` does this), only so
nobody does the same work twice; nobody is assigned areas. When
you finish a task, mark it ☑ and leave a note for the next person.

Status key: ☐ not started · ◐ in progress · ☑ done

#### Check the data

| Task | Why it matters | Due | Who's on it | Status | Notes for the next person |
|---|---|---|---|---|---|
| **Make the main file safe to total in Excel** | The 4 Dec charts add up the dollar column; today that would include money the counting rules leave out | 4 Dec | Tierney | ☑ | Done (branch `sheet/counted-total`, 21 Nov): both files have "Counts toward total?" (Yes/No) and "Amount counted toward total ($)" after "Veto status"; summing the second gives exactly the totals `combine` prints, and `export` prints the sums (DESIGN §7.13, §8 rows 13b–13c; runbook step 7, "Totals in Excel"). Still open from the 4 Dec checklist item: the presentation copy must record which run it came from. Worth telling the partner: these two columns are beyond `exampledata.csv`, as "Veto status" was |
| **Random-row review: draw the sample this week** | People catch what no automatic check can: omissions, errors and judgment calls that should change | 4 Dec | Mario | ◐ | **Sample command built (21 Nov):** `python -m ma_approps sample` writes `reports/random_review_sample.csv`: 200 rows (`--size`) of the main file, spread across fiscal years and funding actions, same rows for the same `--seed`. An "Amount source" column says CTHRU or Law text (about 1 in 4 rows are CTHRU; the rest have no second check). Reviewers fill the blank columns on the right (Matches the law?, What is wrong, Reviewer, Date checked); the file isn't read back. **Still to do:** split the rows among reviewers, check them against the laws, and put each finding in `review/corrections.csv`, `config/line_item_catalog.csv` or a new row here. Everyone must use the same copy of the sample (the main file changes when the program re-runs, so share the file, don't redraw). Leave time to apply findings before 4 Dec (Thanksgiving is 26 Nov) |
| **Random-row review: rows 101–200** (Mario's sample, `random_review_sample_final 2.0.xlsx`) | The second half of the sample | 4 Dec | Tierney | ☑ | Done 22 Nov: 93 of 100 match the law. The 7 that didn't are fixed (branch `check/random-review-b`; details in `review/research_log.md`): two agency headings (now a rule in `label.py`, 63 rows), two policy areas (catalog: 2511-0103, and the Cultural Council's 9 items), VOCA Bridge's 2024 increase counted as state money and 7006-0071's −$25,000 (corrections). The filled-in rows were sent back for Mario's sheet. #160 is an instance of Q30 (override figures) |
| **Build the review queue** (`review/review_queue.csv`, DESIGN §7.12) | Lists every row that needs a person, with the reason; the runbook needs it too | 4 Dec | Tierney | ☑ | Built (branch `b/review-queue`): `export` writes `review/review_queue.csv` every run, 287 rows on the 21 Nov run (DESIGN §7.12, runbook step 6). Next: work it from the top. Known gap: an explanation written only in `review/research_log.md` doesn't take a row off the queue; a way to record "explained" that the program reads would fix that |
| **Let a person mark a review-queue item as explained** | Without it, an explained CTHRU difference, amendment or borrowing limit is listed again on every run, so each year's analyst re-checks it | 4 Dec | Emma | ☑ | Done (branch `check/queue-explanations`, 21 Nov): copy a queue line into `review/queue_explanations.csv` and write why; the next run leaves it off the queue (DESIGN §7.21, runbook step 6). The 41 lines Tierney settled (the 20 amendment changes and the 21 borrowing-limit items) are entered, so the queue is 163 lines on the 21 Nov run: 162 `cthru_mismatch` and 1 `combine_problem` (1599-9817's $300M, FY2022). Use it for every CTHRU difference you explain |
| **Review queue: the 20 amendment changes to confirm** (Q21, Q27) | Each is a later law changing an earlier item's figure; the rules count it $0, and a person confirms that's right | 4 Dec | Tierney | ☑ | Done (branch `check/amendment-review`, 21 Nov; `review/research_log.md`, Decision Log): all 20 confirmed at $0 except 2021-76 §12, which was matched with a §2CI carried-forward balance. Fixed in code, together with figures printed without "$" (`read_amendments` 0.12.0); 2000-0100 and 2310-0200 now match CTHRU. Two Record IDs changed with their action (PURP → RED). All 20 are marked explained in `review/queue_explanations.csv` (21 Nov) |
| **Federal money: flagged and left out of totals everywhere** (Q1) | The partner decided federal money stays in the data but never counts toward totals; money the program doesn't recognise as federal would inflate every total and chart | 4 Dec | Tierney | ◐ | **Part 1 done** (branch `check/federal-funds`, 21 Nov): every fund the laws name is now in `config/funds.csv`. Spelling differences are ignored, three funds were judged state money (Education Fund, Commonwealth Care Trust Fund, Health Safety Net Trust Fund) and the ARPA Coronavirus State Fiscal Recovery Fund is federal, so 2021-22 §3's $4.9B transfer is flagged; the review queue has no `unknown_fund` rows left. **Left: part 2**, the bond items whose federal split the law doesn't state (2020-383 §34, 2021-15 §6, 2022-176 §48, 2024-139 §4), which keep their full amount in the capital total, marked `unknown`: read each law, fix, or record as a known limitation |
| **Per-year totals against CTHRU** (Q28) | The yearly totals are what the partner will compare first | 4 Dec | Tierney | ◐ | **Supplementals FY2021–FY2025 done** (branch `check/q28-cthru`, 21 Nov; Decision Log and `review/research_log.md`): supplemental transfers into trust funds no longer count (5 items, $173.5M), increases to §2D federal grant items are federal, 2022-268's run-in item 1599-1214 is a manual row, and every other FY2021–FY2025 supplemental difference is explained. **Left:** (1) the `retained_revenue` differences, fee-revenue and chargeback items CTHRU doesn't carry (59 `not_in_cthru`, 33 in FY2025, likely issue #36); (2) the 3 FY2021 supplementals ($2.6M); (3) ~~2021-76 §11–§14~~ done: they move $100,000 from 2310-0200 to 2000-0100, now read (amendment review, 21 Nov); (4) FY2026's $1.7B of 2026 laws is a known limitation for the codebook. Earlier: three FY2024 amendment increases explained by Emily H. |
| **Annual budgets: 3 CTHRU mismatches and items read as vetoed** (Q29) | An item wrongly read as vetoed shows $0 | 4 Dec | Tierney | ☑ | Done (branch `check/q29-vetoes`, 21 Nov; DESIGN Q29 in the Decision Log, details in `review/research_log.md`): 61 rows read as vetoed to $0 are now 14. 41 were fee-revenue items (fixed in code), 5 a trust transfer CTHRU doesn't list (fixed in code), 1 an FY2025 override (a correction); 2 of the 3 CTHRU mismatches were CTHRU counting a later supplement twice (corrections). **Left for a person:** confirm the 10 FY2025 items still vetoed against Attachment A of the Governor's FY2025 veto message (listed in the research log); 7061-0033's $2,605 FY2025 difference is unexplained |
| **The other open data questions:** override figures (Q30), 9C cuts (Q32) | Each one changes some rows' amounts, fiscal year or flags | 4 Dec | Emma | ☑ | Done (branch `check/q30-q32`, 24 Nov; Decision Log): a later change to an overridden item is now checked against the amount CTHRU shows restored, which replaces the hand fix for 2024-248 §86 (7006-0071, −$25,000). Q32 needs no change: 9C cuts don't touch the figures we compare. Two known limitations for the codebook: partial overrides show as `overridden`, and amounts don't reflect 9C cuts |
| **The FY2022 budget's §2B year** (Q34) | 36 chargeback rows read with the wrong fiscal year at the source | 4 Dec | Emma | ☑ | Closed, no change needed (24 Nov; Decision Log): the law's §2B introduction itself says fiscal year 2021, and the reader records it as written, but the spreadsheets already show FY2022, because annual rows take the budget's year from the law list. Both spreadsheets were identical before and after trying a fix, so none was added |
| **8 borrowing limits that differ from their items** | The bond file's totals depend on them | 4 Dec | Tierney | ☑ | Done (branch `check/borrowing-limits`, 21 Nov; `review/research_log.md`, Decision Log): 3 gaps are identified federal shares, 3 are vetoes after the limit was set, and 2 are unexplained by the law (2022-176 §48, $17.2M; 2024-139 §4, $400M), kept under Q11's rule and listed as a known limitation for the codebook. Their 21 items are marked explained in `review/queue_explanations.csv` (21 Nov) |
| **Fee-revenue and chargeback items vs CTHRU** (Q31, and [issue #36](https://github.com/EmmaWisniewski/capstone-fall26/issues/36): FY2025 lists only 12 chargeback accounts) | The biggest block of unexplained CTHRU differences left on the review queue (79 of 144 on the 24 Nov run) | 4 Dec | Emma | ☑ | Done (branch `check/fee-revenue-cthru`, 24 Nov): CTHRU books most of these items as an estimate with no ceiling, so the comparison now uses the estimate when there's no ceiling (DESIGN §13 check 4, Decision Log 2026-11-24). Issue #36 is the same thing, not missing accounts. The 17 lines left are marked explained, including 4 known limitations for the codebook. The review queue is 80 lines on the 24 Nov run, none of them fee-revenue |
| **Run with a fresh CTHRU download** | Some checks wait on newer CTHRU data | 4 Dec | Emma | ☑ | Done (13 and 21 Nov, on Emma's computer): with the 13 Nov snapshot, FY2026 is compared, so 2025-9 (the FY2026 budget) is checked like the other budgets, and 2021-102 §2A's fund rule works: 41 rows on the Transitional Escrow Fund count, 12 on the Federal COVID-19 Response Fund don't. The snapshot lives in `data/raw/cthru/` on each computer and isn't shared, so **whoever builds the presentation or final copy runs `python -m ma_approps run --stage cthru` (online) first**. FY2026's 48 `missing_in_data` supplemental differences are 2026 laws, outside the window (Q28's known limitation) |
| **Capital file gaps** | Blank cells need either a fix or an explanation in the codebook | 4 Dec | Emma | ☑ | Re-checked on the 21 Nov run (214 rows): no row lacks an agency any more. 13 rows name no paying fund: the 12 items of 2024-139, whose §4–§6 name none (Emma read the whole law; `review/research_log.md`), and 2024-150 §60, the restated 1993 item, whose 1993 borrowing limit isn't read; that row is also the 1 without a borrowing limit. Both are known limitations for the codebook |
| **Which checks in DESIGN §13 are built?** | A check that's described but not built gives false confidence | 4 Dec | Emma | ◐ | Known not built: catalog drift (check 11), corrections whose Record ID matches no row (check 9). Two completeness tests from the old milestones also need a home: at least 99% of annual-budget items have a description, and `config/manual_rows.csv` is empty or each row is justified (check 10). List the rest, then build what matters or record it as a known limitation |
| **Vetoed wording** | Decides whether struck wording is worth showing | 4 Dec | | ☐ | Tierney was to ask George about uses for vetoed wording (`read_items`' `wording_vetoed`, DESIGN §11.4). Still open? |

#### Edge cases

| Task | Why it matters | Due | Who's on it | Status | Notes for the next person |
|---|---|---|---|---|---|
| **Recurring problems found in review → handled in code** | A pattern that will come back every year must not need a person every year | 4 Dec | | ☐ | Add a row here for each pattern the random-row review or the open questions turn up. A one-time misprint goes in an existing fix file instead (CLAUDE.md, "Automate what recurs"). Known quirks so far: the runbook's appendix and `review/research_log.md` |
| **Vague agency headings** (random-row review) | A heading like "Office of the Secretary." or "TRANSPORTATION." isn't an agency | 4 Dec | Tierney | ☑ | Handled in `label.agency_office` (a bare "Office of the Secretary" takes the line's CTHRU department) and `DEPARTMENT_NAME_FIXES` ("Transportation" → MassDOT): 63 rows. Other heading-only agencies ("Judiciary", "Treasurer and Receiver General") were left as they are: the CTHRU department wasn't better for them |

#### An easy spreadsheet

| Task | Why it matters | Due | Who's on it | Status | Notes for the next person |
|---|---|---|---|---|---|
| **A summary table the program writes** | The 4 Dec charts and the partner need yearly totals by policy area; a total worked out by hand can skip the counting rules (CLAUDE.md) | 4 Dec | Tierney | ☑ | Done (branch `sheet/summary-table`, 27 Nov): `data/output/ma_appropriations_summary_cy….csv`, rewritten every run (DESIGN §7.13; runbook step 7, "Totals in Excel"). Its "All years" operating total equals the main file's counted sum. Ideas if the charts need more: by agency, or one-time vs recurring |
| **Write down what's awkward while making the 4 Dec charts** | The fixes should come from real use, not guesses | 4 Dec | | ☐ | Anyone making the charts: add a line here for each thing that was hard to do in Excel |
| **Fix what's on that list** | The partner and the analyst will work in Excel | 11 Dec | | ☐ | Ideas to weigh: plain words where the file still shows codes; amounts and dates Excel reads as numbers and dates; consistent "Unknown" and "Not classified"; an Excel copy with a frozen header, filters and a short "Read me" tab pointing to the codebook. Any column or value change goes through DESIGN §7.13/§9, `schemas.py` and the Decision Log, within the partner's `exampledata.csv` columns |

#### Re-run and documentation

| Task | Why it matters | Due | Who's on it | Status | Notes for the next person |
|---|---|---|---|---|---|
| **Fewer steps from download to finished file** | The analyst isn't a programmer: every step is an ask | 11 Dec | | ☐ | Includes installation (creating the `.venv`, `pip install`, the macOS hidden-`.venv` fix in the README) |
| **Remove yearly hand edits** | Each one is a chance for the re-run to go wrong | 11 Dec | | ☐ | In `config/settings.toml`: the `[scope]` dates, `discover_years`, and `contact_email` (still Emma's address) |
| **Readable messages and reports** | The analyst has to understand what the program tells them | 11 Dec | | ☐ | The program's messages, `validate`'s output and the report CSVs |
| **Rewrite the runbook for the analyst** | It's a final deliverable, and today it assumes Claude Code | 11 Dec | | ◐ | First draft exists. Remove the **Say:** lines; write step 5 (`cthru`) and step 6's `combine` and `export` parts; explain every flag and review item, and how to edit each fix file (Excel changes `false` and dates when it saves, so the labels part says to use a plain-text editor) |
| **Write the codebook** (`docs/CODEBOOK.md`) | It's a final deliverable: what every column and value means | 11 Dec | | ☐ | Every column of the main and capital files, allowed values, counting rules, flags and known limitations. Starting points: DESIGN §8–§10, `review/research_log.md`, and the plain-language partner page in git history (`docs/plain-language/partner-decisions.md`, deleted 2026-11-18). Written by hand (decided 2026-11-18), plus a test that fails if any column of the main or capital file isn't named in it. Once it's written, trim DESIGN §8–§10's export text so each rule is written once |
| **Re-run test on the 2026 laws** | The only proof someone else can re-run it | 11 Dec | | ☐ | Someone who didn't write the program follows the runbook in the terminal, without Claude Code or code changes, e.g. on 2026-55, 2026-101 and the FY2027 budget; list what broke |
| **The extended file** (DESIGN §7.13) | Nice to have, unless the partner asks for it | 11 Dec | | ☐ | The main file plus every funding-actions column |
| **Publish the final files** | How the partner receives the dataset | 11 Dec | | ☐ | Email the spreadsheet to the partner; attach the main, capital and summary files, plus that run's `reports/law_status.csv` and `reports/validation/` files, to a GitHub release whose notes name the commit they were built from (never commit them; git ignores them anyway). The old snapshot branch `d/dataset-snapshot-2026-11-12` can then be deleted |

Open questions are listed in [DESIGN §19](DESIGN.md#19-open-questions), and decisions in the
[Decision Log](DESIGN.md#20-decision-log).

**Scope decided:** the project covers appropriations (what laws authorized), not what the
state actually *spent*. Our partner set this at the proposal stage
(see the [Decision Log](DESIGN.md#20-decision-log), 2026-11-01).

---

## 6. Where to go next

- **How to work day to day** (branches, commits, pull requests, working with Claude):
  [`WORKFLOW.md`](WORKFLOW.md)
- **What to work on:** the task list above, or type `/start-task` in Claude Code
- **The detail, by topic, in [`DESIGN.md`](DESIGN.md):**
  [§1](DESIGN.md#1-purpose-scope-non-goals) goals and scope ·
  [§3](DESIGN.md#3-sources) sources ·
  [§5](DESIGN.md#5-core-data-model-the-funding-actions-table) the funding actions table ·
  [§6](DESIGN.md#6-pipeline-architecture) the stages ·
  [§7](DESIGN.md#7-file-formats) file formats ·
  [§10](DESIGN.md#10-counting-rules-net-new-appropriation-authority) counting rules ·
  [§11](DESIGN.md#11-parsing-details-and-known-patterns) how laws are read ·
  [§12](DESIGN.md#12-policy-area-classification) policy areas ·
  [§13](DESIGN.md#13-validation-suite) the checks
