# Decisions we need from our partner

*In plain language, for readers with no programming background. A plain-language version of the
open questions in [DESIGN §19](../DESIGN.md#19-open-questions); if the two disagree, §19 is
correct. When the partner answers a question, record the answer in the
[Decision Log (§20)](../DESIGN.md#20-decision-log) and update this page. Last updated
2026-11-06.*

For each question: the question, why it matters, and what the program does until we hear back.
None of these block our work, because the program uses a sensible default for now. But each
answer changes what the final dataset says.

### 1. How should federal money be treated? (§19 Q1) **Decided**
**The answer:** Keep federal money in the dataset, mark it as federal, and leave it out of total
spending. Only money that comes from federal sources is marked: federal grants, COVID relief
(ARPA and the CARES Coronavirus Relief Fund), and two state trust funds that were filled with ARPA
money. State surplus money counts as state money. Under this rule, programs the federal government
later pays back, like MassHealth, count as state money, because the state pays for them from its
General Fund. Our partner decided this, and the group confirmed it. Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-02.

### 2. What counts as "new money"? (Q2) **Decided**
**The answer:** When money is moved into a special fund and spent from it later, it counts once,
when a law spends it, not when it's moved. The move is still listed, but it isn't added to the
totals. Items paid for by fees an agency collects count, and are marked as fee-based. The group
and our partner decided this, keeping the design's counting rules (DESIGN §10). Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-01.

### 3. What do three of the columns mean exactly? (§19 Q3) **Partly decided**
**Decided:** **"Previously funded?"** means funded **in the year before only**. An item counts as
previously funded if it had money in the immediately preceding budget year, and not otherwise,
even if it was funded in some earlier year. Our partner decided this. Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-01.

**Decided:** **"One-time or recurring?"**: recurring means funded in at least 2 budgets in a row.
A program's first year counts if the next year's budget funds it again. Our partner decided this.
Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on 2026-11-02.

**Decided:** **what the placeholder answers mean.** "Unknown" means a fact hasn't been
established; "Not classified" means a category hasn't been assigned; "Pending" means a review or
counting decision is still open. They're only for when we truly don't have enough information.
So the example row that said "Unknown" for a program funded the year before should say "Yes".
Our partner decided this. Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on
2026-11-06.

**Still open:**
- **"New money or re-using existing money?"**
- **Is money a supplemental budget adds to a recurring item recurring or one-time?**

**Why it matters:** these columns appear on every row.

**For now:** we use temporary rules for the open parts (the group chose to keep them on
2026-11-06) and mark them as provisional.

### 4. Should vetoes appear as their own rows? (Q4) **Decided**
**The answer:** No. Each item has one row showing its final amount, after any veto or
restoration, with a note saying whether it was vetoed, reduced or restored. The group decided
this, keeping the default. Recorded in the [Decision Log](../DESIGN.md#20-decision-log) on
2026-11-01. On 2026-11-06 the group added a "Veto status" column to the main spreadsheet, with
two new notes: "partial override" (the Legislature restored only part of a cut) and "wording
vetoed" (wording struck, amount unchanged). The amount before the veto stays in the extended
file. Our partner agreed to the extra column.

### 5. Where should borrowing (bond) laws go? (Q5) **Decided**
**The answer:** In a separate spreadsheet, not the main one. Bond laws authorize borrowing and
spending over several years, so keeping them apart avoids confusing readers about yearly
totals. Our partner decided this. Recorded in the [Decision Log](../DESIGN.md#20-decision-log)
on 2026-11-01. Its columns were decided on 2026-11-06 (question 9).

### 6. What names should we use for each kind of action? (Q8) **Decided**
**The answer:** Our proposed names, such as "Supplemental reduction", "Transfer" and "Capital
authorization", alongside the examples' "Original appropriation" and "Supplemental increase"
(full list in DESIGN §9.2). Our partner approved them. Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-06.

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

**Updated 2026-11-06: federal money in bond laws.** Some projects are partly paid for by the
federal government. When the law says so, the borrowing limit is the state's share and the rest is
federal: in the 2020 transportation bond law, a $4.4 billion highway item has an $880 million
borrowing limit, so $3.52 billion is federal. That federal share is now **left out of the bond
total and marked as federal**, like federal money elsewhere (question 1). When the law doesn't
say how the money splits, the split is marked "unknown" and the full amount stays in. Each
project's full amount, the borrowing limit and the federal share are all kept. Our partner
decided this.

### 9. What should the separate bond spreadsheet look like? (Q16) **Decided**
**The answer:** The same columns as the main spreadsheet, plus 11 more about each project's
borrowing limit: which section sets it, the limit, the total of the projects under it, any federal
share and whether the split is known, a note when the projects and the limit differ, the bond's
name, its longest term, its final repayment date, which fund repays it, and how long the money may
be spent. A law that only restates an old project at the same amount adds no new money. Items the
Governor pocket-vetoed are left out. Decided with our partner. Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-06.

### 10. What extra bond details do you want, and from where? (Q17) **Decided**
**The answer:** Only what the laws themselves say: each bond's longest term, its final repayment
deadline, which fund pays the interest, and how long the money may be spent. No bond sale data
(actual maturity dates and interest rates) and no spending data, so "appropriations only"
(question 7) applies to bonds too. Our partner decided this. Recorded in the
[Decision Log](../DESIGN.md#20-decision-log) on 2026-11-06.

*The question as we asked it:*

**What you asked for:** the separate bond spreadsheet should also show each bond's **maturity
date**, its **interest rate**, and **when the money was spent**.

**What the laws contain:** only part of this. Each bond law sets **limits**: the longest the
bonds can run (for example "not more than 30 years") and a final repayment deadline (for example
"June 30, 2065"). We can include those directly.

**What the laws don't contain:**
- **Actual maturity dates and interest rates** are set later, when the Treasurer sells bonds.
  Those are in the bond sale documents and the state's debt records. One sale often combines
  borrowing from several laws, and one law's borrowing is often spread over several sales, so a
  single bond-law item may not have one interest rate.
- **When the money was spent** is actual spending, which comes from the Comptroller's spending
  records. Our project scope is appropriations only (question 7), so including bond spending
  would be an exception to that decision.

**Our questions for you:** Which of these do you need? At what level: for each line item in a
law, for each borrowing limit, or for each bond sale? And should bond spending be an exception to
"appropriations only"?


---

**Not for the partner (the group decides these itself), still open:** how to date veto overrides
that happen in 2026 for laws passed in 2025 (§19 Q6); how to label a bond row that adds no new
money because a law only restated an old project (§19 Q26); and several technical questions about
how amendments are read (§19 Q19–Q24). The group has decided the others it used to list here:
the two borderline laws (Q7), where bond borrowing limits are stored (Q11), partly restored vetoes
(Q13), the veto column (Q14), and money moved into trusts (Q15, which keeps the default).
