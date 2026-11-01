# Decisions we need from our partner

*In plain language, for readers with no programming background. A plain-language version of the
open questions in [DESIGN §19](../DESIGN.md#19-open-questions); if the two disagree, §19 is
correct. When the partner answers a question, record the answer in the
[Decision Log (§20)](../DESIGN.md#20-decision-log) and update this page. Last updated
2026-11-01.*

For each question: the question, why it matters, and what the program does until we hear back.
None of these block our work, because the program uses a sensible default for now. But each
answer changes what the final dataset says.

### 1. How should federal money be treated? (§19 Q1)
**The question:** Some of the money in state laws comes from the federal government, such as
COVID relief or federal grants. Should we include it, leave it out, or count it separately? And
what about state programs the federal government later pays back, like MassHealth? Does that count
as federal money?

**Why it matters:** It can change the totals by billions of dollars.

**For now:** we keep federal money in the dataset but mark it, and leave it out of the main
totals.

### 2. What counts as "new money"? (Q2) **Decided**
**The answer:** When money is moved into a special fund and spent from it later, it counts once,
when a law spends it, not when it's moved. The move is still listed, but it isn't added to the
totals. Items paid for by fees an agency collects count, and are marked as fee-based. The group
and our partner decided this, keeping the design's counting rules (DESIGN §10). Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-01.

### 3. What do three of the columns mean exactly? (§19 Q3)
**The question:** The example spreadsheet has three yes/no-style columns we need precise
definitions for:
- **"Previously funded?":** funded in the year before? Ever?
- **"One-time or recurring?":** how do we tell which is which?
- **"New money or re-using existing money?"**

One example row also looks inconsistent: it says "Unknown" for a program that state records show
was funded the year before. We'd like to know what was meant.

**Why it matters:** these columns appear on every row.

**For now:** we use temporary rules and mark them as provisional.

### 4. Should vetoes appear as their own rows? (Q4) **Decided**
**The answer:** No. Each item has one row showing its final amount, after any veto or
restoration, with a note saying whether it was vetoed, reduced or restored. The group decided
this, keeping the default. Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on
2026-11-01. The note and the amount before the veto are in the extended file, not the main
spreadsheet. How to show changes to an item's *wording* is still being discussed by the group.

### 5. Where should borrowing (bond) laws go? (Q5) **Decided**
**The answer:** In a separate spreadsheet, not the main one. Bond laws authorize borrowing and
spending over several years, so keeping them apart avoids confusing readers about yearly
totals. Our partner decided this. Recorded in the [Decision Log](../DESIGN.md#20-decision-log)
on 2026-11-01. What columns that separate spreadsheet should have is still open (question 9).

### 6. What names should we use for each kind of action? (§19 Q8)
**The question:** The example rows only show two types: "Original appropriation" and
"Supplemental increase". We've proposed names for the others, such as "Supplemental reduction",
"Transfer" and "Capital authorization". Are these the names the partner wants?

**Why it matters:** these names are what readers see.

**For now:** we use our proposed names (full list in DESIGN §9.2).

### 7. Should we track spending too, not just what laws allowed? (Q10) **Decided**
**The answer:** No. The project covers only what laws *allowed* the state to spend
(appropriations), not what was *actually spent*. Our partner set this scope at the proposal
stage. Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on 2026-11-01; nothing more
is needed from the partner on this.

### 8. When a borrowing law's projects add up to more than it lets the state borrow, which number counts? (Q11) **Decided**
**The answer:** The projects' total. A bond (borrowing) law lists projects with dollar amounts,
and separately limits how much the state may borrow for them. In the 2024 information technology
bond law (2024 Acts, ch. 139), the projects in two sections add up to $1.455 billion, but the law
only lets the state borrow $1.055 billion for them. The dataset reports $1.455 billion, flags the
$400 million difference, and also records the borrowing limits so the two can be compared. Our
partner decided this. Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on
2026-11-01.

### 9. What should the separate bond spreadsheet look like? (§19 Q16)
**The question:** Now that bond laws get their own spreadsheet (question 5), which columns should
it have?

**Why it matters:** It decides how easily readers can compare bond money with the yearly budget
spreadsheet.

**For now:** we plan to use exactly the same 19 columns as the main spreadsheet, with only the
bond rows in it.

---

**Not for the partner (the group decides these itself):** whether two borderline laws belong in
the dataset (2020 ch. 316 and 2021 ch. 9; §19 Q7), how to date veto overrides that happen in
2026 for laws passed in 2025 (§19 Q6), where the program stores each bond law's borrowing
limits and flags their differences (the technical half of §19 Q11), and two follow-ups to the veto decision: whether an item
the Legislature only partly restored counts as "reduced" or "restored" (§19 Q13), and whether the
veto note should also appear in the main spreadsheet (§19 Q14; the partner may have a view, since
the main spreadsheet's columns come from their example). And a follow-up to question 2: some trust
funds can spend money without another law approving it, so under the "count it when a law spends
it" rule, money moved into those funds would never count toward the totals. Should the move count
for those funds instead? (§19 Q15; the partner may have a view.)
