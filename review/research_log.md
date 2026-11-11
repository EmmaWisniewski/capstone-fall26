# Research log

Reasoning behind review decisions that takes more than one line (DESIGN §14).
Add a heading per Record ID, e.g. `## 2023-077-S178-2330-0100-INC-1`, with your name and the date.

## Sources: 1993 ch. 52 and 1993 ch. 494 (reference-only)
Emma, 2026-11-04.

Both laws are older than the Legislature's API, so the program can't download them. 2024 ch. 150
amends both: §60 replaces item 4000-8200 of ch. 52, and §61 changes the wording of item 3722-8899
of ch. 494. Their text was downloaded from the Massachusetts State Archives as .txt and saved in
`review/sources/` (`1993-52.txt`, `1993-494.txt`). The law-list rows were checked against the
archives' PDFs.
- 1993 ch. 52: https://archives.lib.state.ma.us/entities/archivalmaterial/ffd2412a-7b2f-4316-865b-2b260ebf2c15
- 1993 ch. 494: https://archives.lib.state.ma.us/entities/archivalmaterial/96ff9af7-8661-445e-9b99-e6dbca5ac4be

The .txt files come from scanned pages and have small scanning errors (e.g. "chapter 12 IB" for
121B). Check figures against the PDFs. Both laws' items add up exactly to their borrowing limits:
$54,100,000 (ch. 52 §8) and $295,000,000 (ch. 494 §6).

**What the 2024 amendments change**
- **Item 4000-8200** (community-based housing loans for people with mental illness or intellectual
  disabilities): $50,000,000 in 1993 ch. 52 §2; replaced at the same $50,000,000 by 1993 ch. 494
  §4; amended by 2002 ch. 244 §15–18, wording only: §15 raises the loan limit in clause (1) from
  thirty to 50 percent of total development costs; §16 requires the use restriction to be recorded
  in the registry of deeds or the registry district of the land court of the county where the
  property is; §17 sets eligibility by the departments of mental health and mental retardation,
  with release on repayment or foreclosure; §18 allows loan extensions in 10-year periods if the
  housing is still needed. Replaced again by 2024 ch. 150 §60 at $50,000,000. **So the amount was
  $50,000,000 throughout.** 2002 ch. 244 is in the Legislature's API and listed as reference-only.
  (2002 changes checked against the 1993 wording by Emma, 2026-11-05.)
- **Item 3722-8899** (loans for alternative forms of housing, $30,000,000 in 1993 ch. 494 §2): 2024
  ch. 150 §61 rewrites the condition in its clause (2) for releasing a property's use restriction.
  The 1993 text allowed release only when the loan is repaid or a foreclosure deed is recorded;
  2024 adds a third option, a **disposition of the property**, provided the executive office of
  housing and livable communities determines that clients will be better served at an
  alternative property, and the proceeds are used, as needed to replace the housing, to acquire
  or rehabilitate that alternative property. It changes wording only, not dollars. (Wording
  checked against the official text by Emma, 2026-11-04.)

## 2021-029-S49-1595-1068-INC-1 and 2023-077-S81-3000-7040-INC-1 (Q27)

Emily H., 2026-11-08. Emma's review of PR #17 asked whether FY2021 item 1595-1068 is counted twice.

- **2021 ch. 29.** §2 supplements FY2021 item 1595-1068 by $31,937,236. §49 amends the same item in the
  FY2021 GAA (2020 ch. 227, §2E), striking "$505,250,000" and inserting "$537,190,000" (+$31,940,000).
  (§48 changes a different figure in the item's text, a cap of "up to $437,750,000" on payments to the
  Cambridge Public Health Commission, to $465,350,000. That's a limit inside the item, not its total; see Q21.)
- **CTHRU, FY2021, 1595-1068:** original $505,250,000; supplemental $31,937,236; total $537,187,236.
  So CTHRU counts §2's amount once. §49's $537,190,000 is that total rounded up to the nearest $10,000:
  §49 restates the item's figure to include §2's money.
- **The same pattern in 2023 ch. 77:** §2 supplements FY2023 item 3000-7040 (a retained-revenue item)
  by $200,000, and §81 amends the FY2023 GAA (2022 ch. 126) item from $320,000 to $520,000. CTHRU,
  FY2023: one retained-revenue ceiling of $520,000 and no supplemental.
- In the laws cached locally (9 laws plus the 8 samples), these are the only two cases where one law
  both supplements an item in §2 and changes the same item's figure in an outside section.
- **Update, 2026-11-08:** with 16 laws downloaded, the struck-figure check (DESIGN §13 check 3) flags
  two more, both in 2024 ch. 206 and both retained-revenue items in the FY2024 GAA (2023 ch. 28):
  §33 raises 1775-0700 from $200,000 to $600,000 while §2 adds $400,000, and §39 raises 8100-0102
  from $45,000,000 to $52,000,000 while §2 adds $7,000,000. CTHRU, FY2024: ceilings of $600,000 and
  $52,000,000, with no supplemental, so again the money appears once.

Conclusion: count the §2 row only; the outside section restates it. Proposed as a general rule in DESIGN Q27.

## Sections returned with a recommendation of amendment, or vetoed (Q23)

Emily H., 2026-11-08. `read_amendments` listed five outside sections as "looks vetoed". The law text
and each bill's history on malegislature.gov (`/api/GeneralCourts/{court}/Documents/{bill}/DocumentHistoryActions`)
show that four of them were not vetoed: the Governor **returned them with a recommendation of
amendment**. A returned section isn't law in the chapter that prints it. The Legislature acts on it
as a separate bill, and its version becomes a separate chapter.

| Section | Printed in | What happened | Became law in |
|---|---|---|---|
| §22: $75,000,000 of federal COVID-19 money to the COVID-19 Emergency Paid Sick Leave Fund | 2021 ch. 9 (H90) | H3702: Governor's amendment rejected, House amendment adopted, re-enacted | **2021 ch. 16** §13 ($75,000,000), May 28, 2021 |
| §74: replaces item 8100-1014 of 2019 ch. 5 (sexual assault evidence kits) | 2021 ch. 24, FY2022 GAA (H4002) | H4013 (with §119): Governor's amendment rejected, re-enacted | **2021 ch. 35** §1, Aug 3, 2021 (already a sample and on the law list) |
| §102: $250,000,000 to the Pension Liability Fund | 2021 ch. 24 | H4004 (with §7, §103): Governor's amendment rejected, re-enacted | **2021 ch. 33** §2: "no less than" $250,000,000, on a monthly schedule, if FY2022 revenues meet the estimates, Aug 3, 2021 |
| §103: $350,000,000 to the Student Opportunity Act Investment Fund | 2021 ch. 24 | H4004 | **2021 ch. 33** §2: "no less than" $350,000,000, same condition |
| §100: $205,000,000 transfer from the federal COVID-19 response fund or the Transitional Escrow Fund | 2023 ch. 28, FY2024 GAA (H4040) | **Disapproved** (a veto). H4040's history lists override votes on many items but none on §100 | never: the veto stands |

What follows:
- Reader 0.9.0 gives no rows for a section returned with a recommendation of amendment, and lists it
  as unread when it would otherwise have given rows. That keeps 2021-24 §74 from counting alongside
  2021-35 §1, and §102–§103 alongside 2021 ch. 33 once that law is listed.
- **2021 ch. 16 and 2021 ch. 33 aren't on the law list** (nor in PR #34). Both hold the enacted
  versions of these transfers, so workstream A should consider adding them. All of these are
  transfers into funds, which don't count toward the operating totals (Q2), so the totals don't change.
- 2023-28 §100 keeps its `low` confidence row; `combine` should leave it out as vetoed.

## Misprint in 2024 ch. 248 §35 (amendment target 2022-24)
Emma, 2026-11-08.

2024 ch. 248 §35 reads "Item 8200-0200 of section 2 of chapter 24 of the acts of 2022 is hereby amended
by striking out the figure "2024", inserted by section 50 of chapter 77 of the acts of 2023, and
inserting in place thereof the following figure:- 2025." Item 8200-0200 is in **2021** ch. 24 (the FY2022
GAA): 2023 ch. 77 §50, which §35 cites, amends it there ("said chapter 24", resolved to 2021-24), and
2022 ch. 24 (a Northampton conservation easement act) doesn't contain the item. So §35 means 2021 ch. 24.
`read_amendments` follows the text, so it attaches this date extension (2024 → 2025) to 2022-24; the
target needs correcting on that side. 2022-24 is excluded from the law list.

Corrected on the reading side by Emily H., 2026-11-09: `config/citation_fixes.csv` (DESIGN §7.18) maps
2024-248 §35's citation of 2022-24 to 2021-24, so reader 0.10.0 attaches the date extension to
2021-24 with `medium` confidence.
