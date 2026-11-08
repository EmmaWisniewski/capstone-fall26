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

## Misprint in 2024 ch. 248 §35 (amendment target 2022-24)
Emma, 2026-11-08.

2024 ch. 248 §35 reads "Item 8200-0200 of section 2 of chapter 24 of the acts of 2022 is hereby amended
by striking out the figure "2024", inserted by section 50 of chapter 77 of the acts of 2023, and
inserting in place thereof the following figure:- 2025." Item 8200-0200 is in **2021** ch. 24 (the FY2022
GAA): 2023 ch. 77 §50, which §35 cites, amends it there ("said chapter 24", resolved to 2021-24), and
2022 ch. 24 (a Northampton conservation easement act) doesn't contain the item. So §35 means 2021 ch. 24.
`read_amendments` follows the text, so it attaches this date extension (2024 → 2025) to 2022-24; the
target needs correcting on that side. 2022-24 is excluded from the law list.
