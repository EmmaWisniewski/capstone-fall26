# Runbook: adding a new year of laws

*For a future group that wants to add the next year's laws to the dataset. Written in plain
language for readers who are new to programming. You'll work through Claude Code, as the
fall 2026 group did; the **Say:** lines are things you can type to it. If this runbook and
[`DESIGN.md`](DESIGN.md) disagree, DESIGN is correct, and please fix the runbook.*

*Status: first draft (workstream A, 2026-11-07; updated 2026-11-11 after Tierney's review). Steps
1–4 describe stages that are built and merged. Step 5 waits on workstream E (the `cthru` stage is
merged, #21). Step 6 is a placeholder while `combine`, `label` and `export` are built (the shared
core of `combine` and the capital file are in review, #43 and #44). Milestone M6 is a test of this
runbook: someone who didn't write it follows it on the 2026 laws and lists what broke.*

Each step has three parts: **what to do**, **what to check**, and **if something's wrong**.

---

## 0. Before you start

**What to do**
1. Read [`OVERVIEW.md`](OVERVIEW.md) (15 minutes) and the first half of
   [`WORKFLOW.md`](WORKFLOW.md) (how branches, commits and pull requests work).
2. Set up your computer:
   > **Say:** "Set up this repo for me following the Quickstart in README.md, and run the tests."
3. **Replace the contact email.** The program tells malegislature.gov who is downloading, using
   `contact_email` in `config/settings.toml`. It still holds the fall 2026 group's address. Put in
   your group's address. The site may treat it as public record, and the repository is public.
   Record the change in the Decision Log (DESIGN §20), as Q18 was.
4. Make a branch for the year's work, e.g. `a/add-2026-laws`.

**What to check:** `pytest` and `python -m ma_approps validate` pass before you change anything.
If they don't, fix that first, so you know later failures come from the new year.

**If something's wrong:** on a Mac, if `python -m ma_approps` says "No module named ma_approps",
the Mac has hidden the project's setup folder. Run `chflags -R nohidden .venv` and try again (the
README's macOS tip; the fall 2026 group hit this several times).

**Rough time:** step 2 takes the longest for people, because every candidate law needs a
decision. The program's own run takes minutes.

---

## 1. Tell the program about the new year

**What to do:** in `config/settings.toml`, under `[scope]`:
- add the new Acts volume to `discover_years`, plus the year after it (laws approved next year
  can still belong to this year's budget, and the other way round);
- **the fiscal years for the annual budget data need no change.** The `cthru` stage works them out
  from the `primary_fy` column of the law list, so the new year's laws bring their fiscal year with
  them in step 2. `cthru_fiscal_years` is there only to force a specific list, and is normally left
  commented out;
- decide with your group whether the dataset's **approval window** (`approved_from`,
  `approved_to`) grows to include the new year. The capital file's name (`…_cy2021_2025.csv`)
  follows the window automatically; check that the main file's name does too. That's one of the
  things M6 is meant to find.

**What to check:** nothing else in the code mentions a year. The program is meant to have no
years written into it (CLAUDE.md, "Nothing may be hard-coded to 2021–2025"). If you find one,
that's a bug: open an issue.

---

## 2. Find and download the new laws (`laws` stage)

**What to do**
> **Say:** "Run `python -m ma_approps run --stage laws` and tell me which new candidate laws it
> found."

The stage:
1. downloads the list of every law for each year in `discover_years` (one request per year,
   about one per second, saved in `data/raw/`, which is never committed);
2. checks each law **not already on the law list** for signs that it spends money:
   - a budget line item;
   - "hereby appropriated";
   - an amendment of a line item;
   - borrowing ("issue and sell … bonds");
   - the comptroller transferring a dollar amount ("the comptroller shall transfer $…");
   - an appropriation-style title.
3. adds each match to `config/law_list.csv` with `role = tbd`, recording which signs matched;
4. adds **amendment targets**: every law that an in-scope law amends but the list lacks, also as
   `tbd`, with a reason like "Amendment target: amended by 2021-102 §46". These usually become
   `reference_only`. They come from the previous run of `read_amendments`, so **run `laws` again
   after step 3** and decide any new ones;
5. downloads the text of every listed law that isn't `excluded`.

It never changes a row that's already there, so earlier groups' decisions stay as they were.

**Then decide every `tbd` row.** This is the most important human step. For each candidate,
read the law (`https://malegislature.gov/Laws/SessionLaws/Acts/<year>/Chapter<number>`) and set
`role`:

| Decision | When | Examples (fall 2026 review) |
|---|---|---|
| `in_scope` | approved inside the window and it appropriates money, changes an item's amount, or changes an item (even only its wording) | 2022 ch. 83 adds an $8M earmark to a budget item |
| `reference_only` | approved **outside** the window, but needed for calculations: the annual budget of the year before (for "Previously funded?"), a same-fiscal-year law, or a law whose items an in-window law **actually amends** | 2020 ch. 124 (an in-window law amends its item 1599-1232) |
| `excluded` | not needed | interim budgets outside the window; laws that in-window laws cite only in history notes |

Also fill in `law_type` (§9.1), a short `law_name`, `primary_fy` where it has one, an
`include_reason`, and a note like "Reviewed by <name>, <date>: …".

**Two traps the fall 2026 group hit:**
- **A mention isn't an amendment.** "Item 7008-1116 of chapter 41 of the acts of 2019, *inserted
  by section 29 of chapter 201 of the acts of 2020*, is hereby amended" amends 2019 ch. 41, not
  2020 ch. 201. Read the sentence before marking a law reference-only.
  > **Say:** "Show me the exact sentences in in-window laws that cite <law>."
- **The volume year isn't the approval year.** 2020 ch. 358 is in the 2020 volume but was
  approved in January 2021, so it's inside a 2021–2025 window. Decide by `approved_date`.

**What to check**
- `python -m ma_approps validate` reports no law-list problems. (It checks, for example, that
  `reference_only` laws really were approved outside the window.)
- Running the stage again finds **0 new candidates**.

**If something's wrong**
- **A law is too old for the Legislature's API** (the 1993 laws were): find its text on the
  Massachusetts State Archives' website, https://archives.lib.state.ma.us/. Old session laws can be
  searched and downloaded there as .txt or PDF, so there's no need to visit the archives in
  person. Save the .txt in `review/sources/` (named like `1993-52.txt`), add the row by hand with
  `parse_strategy = manual` (the downloader then skips it), and record the archive link in
  `review/research_log.md`. The .txt comes from scanned pages, so check any dollar figure against
  the PDF.
- **A law you expected isn't a candidate:** add it by hand, and open an issue so the signs can be
  improved.
- **Many candidates look wrong:** the signs may need tightening, as in 2026 (Decision Log,
  2026-11-07). Open an issue rather than excluding dozens by hand.

---

## 3. Read the laws (`read_items`, `read_bonds`, `read_amendments`)

**What to do**
> **Say:** "Run the read_items, read_bonds and read_amendments stages and summarize what each
> found, including anything left unread."

| Stage | Reads | Writes |
|---|---|---|
| `read_items` | line items in annual budgets and supplemental budgets | `data/interim/items_raw.csv` |
| `read_bonds` | items and borrowing limits in bond laws, and capital sections in other laws | `data/interim/bond_items_raw.csv`, `bond_authorizations_raw.csv` |
| `read_amendments` | sections that change earlier laws, and interim budgets | `data/interim/amendments_raw.csv` |

**What to check**
- The **unread reports** in `reports/` (`unread_paragraphs.csv`, `unread_paragraphs_bonds.csv`,
  `unread_sections.csv`). Every row there is something the program couldn't read. Each must be
  either fixed or explained before the year is done.
- **Then run `laws` again** (step 2): `read_amendments` may have found amendments of laws that
  aren't on the law list yet. Decide the new `tbd` rows, then run step 3 once more.

**If something's wrong**
- **Many unread rows of the same kind:** the law format changed. That's a code fix in the stage's
  reader. Open an issue for its owner (see OVERVIEW §3), with an example.
- **A misprinted item number** in the law (like "911-1003", which should be 5911-1003): add a row
  to `config/item_number_fixes.csv` (DESIGN §7.17), so the item is read with the right number.
- **A misprinted law citation** in an amending section (2024 ch. 248 §35 cites 2022 ch. 24 for an
  item that's in 2021 ch. 24): add a row to `config/citation_fixes.csv` (DESIGN §7.18).
- **Any other odd paragraph or section** (a local-aid formula, a revenue declaration, a section
  that needs no row): explain it in `review/unread_explanations.csv` (DESIGN §7.19, decided in Q22),
  one row per unread row: which `report` it's in (e.g. `unread_sections.csv`), its `law_key` and
  `section`, a plain-language `explanation` (what the section does and why it needs no row, or
  where its money is counted instead), `explained_by` and `date`. Never edit the report itself:
  it's regenerated on every run. `validate` counts a row as explained when this file has a match.
  > **Say:** "List the unread rows that aren't explained yet, with each section's text, so I can
  > write the explanations."

---

## 4. Check the bond laws

**What to do**
> **Say:** "Compare each borrowing limit in bond_authorizations_raw.csv with the items it covers,
> and list every difference with the reason."

A bond law lists projects (items) and, separately, how much the state may borrow for them
(borrowing limits). The program records both (DESIGN §7.16).

**What a normal difference looks like** (all seen in 2021–2025):
- **Items less than the limit:** an item was reduced by veto, or pocket-vetoed. Pocket-vetoed
  items never became law, so they count $0 and are left out of the bond spreadsheet.
- **Items more than the limit:** usually federal money.
  - `identified`: the item may only be spent "based upon a prior or anticipated future
    commitment of federal funds", so the limit is the state's share, and the federal share is
    items − limit. It's left out of the capital total (example: 2020 ch. 383 item 6121-2114, $4.4B
    of items, $880M limit, $3.52B federal).
  - `unknown`: federal money is expected but the law gives no amount: borrowing that depends on
    federal reimbursement (2021 ch. 15 item 4000-2026), notes that cover only "a portion" of the
    costs (2020 ch. 383 §34), or a gap the law doesn't explain (2024 ch. 139 §4). It stays in the
    total, flagged.

**What to check:** spot-check at least five borrowing limits and five items against the law
text: amount, sections or items covered, bond name, maximum term, final date, paying fund, and
how long the money may be spent. The fall 2026 group's spot-checks found real problems (a kind of
borrowing the survey had missed; spending end dates that differ by section).

**If something's wrong**
- **A difference with no explanation:** read the law around the items and the borrowing section.
  Record what you find in `review/research_log.md`.
- **A new kind of borrowing or wording:** open an issue for workstream A's `read_bonds`, with the
  law and section.

---

## 5. Annual budgets from the Comptroller (`cthru` stage)

*To be written by workstream E (the `cthru` stage is merged, #21). It should cover: running it,
the dated snapshot it saves, and how to read its comparison with the law text.*

---

## 6. Combine, label, review and export

*To be written as the `combine`, `label` and `export` stages are built. It should cover:*
- *running them;*
- *working through `review/review_queue.csv` (new line items needing a policy area, CTHRU
  mismatches, bond-limit differences);*
- *where fixes go: `config/line_item_catalog.csv` for policy areas that apply every year,
  `review/corrections.csv` for one-row fixes, `review/research_log.md` for reasoning. Never edit
  a generated file by hand.*

---

## 7. Validate and publish

**What to do**
> **Say:** "Run pytest and python -m ma_approps validate, and explain anything that isn't clean."

**What "done" looks like**
- tests pass, and `validate` reports no problems;
- every unread report is empty or explained;
- every CTHRU difference is explained or flagged;
- `config/manual_rows.csv` is empty, or each row is justified (see step 8).

**Then record the year:**
- add Decision Log entries for anything you decided (DESIGN §20);
- update the Status Board (§21) and the tracker in OVERVIEW §5;
- open a pull request and get one teammate's review (WORKFLOW §3).

---

## 8. When something breaks

- **Prefer fixing the reader to typing data in.** The project's rule is "automate, don't
  hand-annotate". If a kind of law can't be read, the reader should learn it, so next year's
  group doesn't hit the same problem.
- **`config/manual_rows.csv` is an escape hatch** for a true one-off that no reader should
  handle. Each row needs the exact source text (`source_quote`), who entered it and when.
  `validate` counts these rows; the target is zero.
- **Write down your reasoning** in `review/research_log.md` whenever a decision took more than one
  line.
- **Open a GitHub issue** for anything you can't fix, with the law, the section and what you
  expected. Assign it to the stage's owner if there still is one.

---

## Appendix: known quirks of Massachusetts laws

- **Volume year vs. approval year:** a law's Acts volume (the "2020" in "2020 ch. 358") can differ
  from the year it was approved (January 2021). The program uses the volume for the law key and
  the approval date for the window.
- **"Approved in part":** the Governor can veto some sections and sign the rest. The law's status
  says so (e.g. 2002 ch. 244, 1993 ch. 52).
- **Inline veto markup** (crossed-out text) is a hint, not proof: the Legislature may have
  overridden the veto later (DESIGN §11.4).
- **Some old laws aren't in the Legislature's API**: 1993's weren't, 2002's were. The State
  Archives' website (https://archives.lib.state.ma.us/) has text and PDFs.
- **Mistyped item numbers** occur in the official text (e.g. "911-1003", which is missing a digit;
  issue #18). They're corrected in `config/item_number_fixes.csv`.
- **Misprinted law citations** occur too (2024 ch. 248 §35 cites the wrong chapter). They're
  corrected in `config/citation_fixes.csv`.
- **Spending end dates can differ by section** within one bond law (2024 ch. 238).
- **Not all borrowing is "bonds":** 2020 ch. 383 §34 authorizes "federal grant anticipation notes",
  repaid from federal highway money.
- **Bond agency headings can mislead:** in 2022 ch. 140, two items sit under a Children and
  Families heading although they're higher education and public safety projects.
