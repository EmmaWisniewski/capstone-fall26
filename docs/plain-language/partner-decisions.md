# Decisions we need from our partner

*In plain language, for readers with no programming background. A plain-language version of the
open questions in [DESIGN §19](../DESIGN.md#19-open-questions); if the two disagree, §19 is
correct. When the partner answers a question, record the answer in the
[Decision Log (§20)](../DESIGN.md#20-decision-log) and update this page. Last updated
2026-10-28.*

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

### 2. What counts as "new money"? (§19 Q2)
**The question:** Sometimes money is moved into a special fund in one law and spent from that
fund in another. Some agencies are allowed to spend fees they collect themselves. Should these
count as new spending, and how do we avoid counting the same dollars twice?

**Why it matters:** Counting money twice would make totals look bigger than they really are.

**For now:** we follow the counting rules in the design (§10), which count the money when it's
spent rather than when it's moved, and mark the fee-based items.

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

### 4. Should vetoes appear as their own rows? (§19 Q4)
**The question:** When the governor cuts or rejects part of a budget, and the Legislature sometimes
restores it, should each of those steps be its own row? Or should a row just show the final
amount, with a note saying a veto happened?

**Why it matters:** Separate rows show the back-and-forth but make the dataset bigger and harder
to collect.

**For now:** one row per item showing the final amount, with a note saying whether it was
vetoed, reduced or restored.

### 5. Where should borrowing (bond) laws go? (§19 Q5)
**The question:** Bond laws authorize the state to borrow money and spend it over several years,
which is different from a yearly budget. Should they be in the same spreadsheet as everything
else, or in a separate one?

**Why it matters:** Mixing them in could confuse readers about yearly totals.

**For now:** same spreadsheet, clearly labeled "Capital authorization", never added into the
yearly budget totals, with a separate total of their own.

### 6. What names should we use for each kind of action? (§19 Q8)
**The question:** The example rows only show two types: "Original appropriation" and
"Supplemental increase". We've proposed names for the others, such as "Supplemental reduction",
"Transfer" and "Capital authorization". Are these the names the partner wants?

**Why it matters:** these names are what readers see.

**For now:** we use our proposed names (full list in DESIGN §9.2).

### 7. Should we track spending too, not just what laws allowed? (§19 Q10)
**The question:** Right now we record what laws *allowed* the state to spend. The state's records
also show what was *actually spent*. Should the project cover that too, and how far?

**Why it matters:** this is the biggest scope question. It could make the project much more
useful, and much bigger.

**For now:** we cover only what laws allowed. Mario (workstream E) is leading this discussion
(DESIGN §16), and it should be decided before milestone M2.

### 8. When a borrowing law's projects add up to more than it lets the state borrow, which number counts? (§19 Q11)
**The question:** A bond (borrowing) law lists projects, each with a dollar amount. Separately,
it sets a limit on how much the state may borrow to pay for them. Usually the two match. But in
the 2024 information technology bond law (2024 Acts, ch. 139), the projects in two of its
sections add up to **$1.455 billion**, while the law only lets the state borrow **$1.055
billion** for them: **$400 million less**. Nothing in the law explains the difference. Which
number should the dataset report as the money this law authorized: the projects' total, or the
borrowing limit?

**Why it matters:** It changes this one law's total by $400 million, and the same thing may
happen in other bond laws we haven't checked yet.

**For now:** each project is listed with its amount as printed, so this law's total is the
projects' total ($1.455 billion). The $400 million difference is flagged for review, and we also
record the borrowing limits so the two can always be compared.

---

**Not for the partner (the group decides these itself):** whether two borderline laws belong in
the dataset (2020 ch. 316 and 2021 ch. 9; §19 Q7), how to date veto overrides that happen in
2026 for laws passed in 2025 (§19 Q6), and where the program stores each bond law's borrowing
limits (the technical half of §19 Q11).
