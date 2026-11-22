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
| §113: $94,000,000 of item 1595-6370 as operating assistance for regional transit authorities (added 2026-11-11) | 2021 ch. 24 | H4014: re-enacted, vetoed, passed over veto 2021-09-30 | **2021 ch. 73**. It only earmarks money already in the item, so it gives no row either way |
| §174: $20,000,000 to the Massachusetts Community Preservation Trust Fund (added 2026-11-11) | 2022 ch. 126, FY2023 GAA (H5050) | H5131: returned again with a recommendation of amendment; "No further action taken" 2023-01-03 | never |
| §100: $205,000,000 transfer from the federal COVID-19 response fund or the Transitional Escrow Fund | 2023 ch. 28, FY2024 GAA (H4040) | **Disapproved** (a veto). H4040's history lists override votes on many items but none on §100 | never: the veto stands |

What follows:
- Reader 0.9.0 gives no rows for a section returned with a recommendation of amendment, and lists it
  as unread when it would otherwise have given rows. That keeps 2021-24 §74 from counting alongside
  2021-35 §1, and §102–§103 alongside 2021 ch. 33 once that law is listed.
- **2021 ch. 16 and 2021 ch. 33 aren't on the law list** (nor in PR #34). Both hold the enacted
  versions of these transfers, so workstream A should consider adding them. All of these are
  transfers into funds, which don't count toward the operating totals (Q2), so the totals don't change.
- 2023-28 §100 keeps its `low` confidence row; `combine` should leave it out as vetoed.
- 2026-11-11 (Emily H.): every unread section now has an explanation in `review/unread_explanations.csv` (Q22), including these.

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

## No paying fund named in 2024 ch. 139 §4–§6 (FutureTech Act)
Emma, 2026-11-10.

In the capital file, the 12 items of 2024 ch. 139 (the FutureTech IT bond, one of the two bond samples)
have an empty "Fund paying the bonds". Their three borrowing-limit sections, §4 ($1,055,000,000 for §2A
and §2B), §5 ($175,000,000 for §2C) and §6 ($26,989,000 for §2D), give the bond name ("FutureTech Act
of 2024"), the maximum term and the final payable date, but **don't say which fund pays the bonds**, as
most bond laws do ("payable from the General Fund…"). Nothing else in the law names one either: the
only mentions of debt service are agencies' project savings sent to the treasurer. Emma read the whole
law and confirmed this. So `read_bonds` is right to leave `paying_fund` empty, and the blank follows the
rule of not assuming the General Fund when a law doesn't name the fund.

## Amendment increases CTHRU doesn't show (Q28)
Emily H., 2026-11-11. The CTHRU comparison in `validate` (§13 check 4, PR #51) lists three FY2024
increases made by outside sections that CTHRU doesn't carry:

| Row | The law | CTHRU, FY2024 |
|---|---|---|
| `2023-077-S182-4512-0205-INC-1` (+$100,000) | 2023 ch. 77 §182 raises item 4512-0205 of the FY2024 GAA (2023-28) from $5,295,000 to $5,395,000; §181 raises the item's earmark for One Life at a Time, Inc. from $100,000 to $200,000 to match | original $5,295,000, no supplemental |
| `2023-077-S191-8324-0050-INC-1` (+$1,750,000) | 2023 ch. 77 §191 raises item 8324-0050 from $3,316,700 to $5,066,700 | original $3,316,700, no supplemental (and a $1,658,350 9C cut) |
| `2024-248-S60-1599-0026-INC-1` (+$25,000) | 2024 ch. 248 §60 raises item 1599-0026 from $16,300,000 to $16,325,000 | original $16,300,000 plus 2024-248 §2's $12,673,961, but not the $25,000 |

What was checked:
- Each struck figure equals the item's printed amount (§13 check 3: `match`), so the reader is right.
- Both bills were signed without vetoes (H4204 and H5077 histories: "Signed by the Governor"), and
  neither law's text has veto markup.
- No CTHRU account shows a supplemental of these amounts in FY2023 to FY2026 (CTHRU snapshot of
  2026-11-11), so the money wasn't booked to another account or year.
- CTHRU does carry other changes of the same kind: 2023-77 §178 (EX-004, +$350,000 to 2330-0100) is in
  its FY2024 supplemental, and so are the other outside-section changes of these two laws, apart from
  2024-248 §126 (a §2B chargeback, which CTHRU shows only as a ceiling; issue #36).

Conclusion: the rows keep the law's amounts. For an amendment the amount is the law's
(`amount_source = law_text`, DESIGN §5.7), and the law is in force. They add $1,875,000 to the FY2024
total that CTHRU doesn't show, so check 4 keeps listing them; this entry is the explanation. If the
group wants CTHRU's figure instead, that is a §5.7 change.

## Manual row: 1993 ch. 52 item 4000-8200 (starting amount for 2024 ch. 150 §60)
Emma, 2026-11-11.

`config/manual_rows.csv` holds one row: 1993 ch. 52 §2 item 4000-8200 at $50,000,000, as a `CAP`
row. 1993 ch. 52 predates the Legislature's API, so no reader can read it (its text is in
`review/sources/1993-52.txt`, checked against the State Archives PDF). The row exists only to give the
item its starting amount: `combine` leaves it out of the funding actions because 1993-52 is
reference-only, and uses it in the running amounts, so 2024 ch. 150 §60, which replaces the item at
the same $50,000,000, becomes a `CAP` row of $0 (2026-11-06 decision; Q26, decided 2026-11-11, keeps a restated bond item as `CAP` $0, labeled "New" and "One-time").

## Annual items read as vetoed to $0, and 3 CTHRU mismatches (Q29)

*Tierney, 2026-11-21; all 70 laws, CTHRU snapshot 2026-11-12.* The program read an annual-budget item
as vetoed to $0 whenever CTHRU had no amount for it: 61 rows (FY2022–FY2026: 11, 10, 9, 19, 12). The
law text marked none of them vetoed except four FY2026 items. They were:

- **41 fee-revenue items, not vetoes.** The agency "may expend", "may retain" or "may collect and
  expend" fees up to a limit, worded in ways the reader didn't recognise ("not to exceed", "up to",
  "may retain not more than"), or "shall expend not more than … from fees" (7061-9601). CTHRU books
  most of them only as a fee-revenue limit. Fixed in code: `read_items` reads the other wordings
  (reader 0.2.1), and `combine.annual_rows` takes CTHRU's own limit when the wording still isn't read.
  They now carry their limit as `retained_revenue_ceiling` rows.
- **1595-4512, a $12.5M–$20M transfer to the Behavioral Health Outreach, Access and Support Trust
  Fund (§2E), every year.** CTHRU never lists it and no budget marks it vetoed. Fixed in code: a §2E
  item CTHRU doesn't list and the law doesn't mark vetoed keeps its printed amount, flagged
  `cthru_mismatch`. Trust transfers never count toward totals, so no total changes.
- **1231-1000 in FY2025 (Sewer Rate Relief Fund, $1,500,000): overridden, not vetoed.** H.4800's
  history shows it passed over veto on 30 Jul 2024; CTHRU has no FY2025 row for it. Fixed by two rows
  in `review/corrections.csv` (amount and veto status).
- **10 FY2025 items stay vetoed at $0, to confirm.** The FY2025 text marks no vetoes, and H.4800's
  history shows only three overrides (1231-1000, 2511-0100, 2511-0111), so these weren't overridden:
  1599-0107, 1599-3856, 1599-7114, 4000-0051, 4512-2020, 7002-0020, 7010-1194, 7061-9406, 7061-9412,
  7061-9650. Confirm each against Attachment A of the Governor's FY2025 veto message (not on
  malegislature.gov's H.4935 page, which covers only Attachments B and C). 7061-9406 was also vetoed
  in FY2026.
- **4 FY2026 items are real vetoes:** 3000-1049, 5095-0017, 7008-1300 and 7061-9406, each marked
  disapproved in 2025-9's text.

**The 3 CTHRU mismatches.** In FY2023, CTHRU's `original_enacted` for **2300-0100** ($1,259,379) and
**7008-1116** ($17,267,500) already includes 2022-268's later increases (§232 +$100,000, §238
+$50,000), which have their own `INC` rows, so taking the CTHRU figure counted that money twice.
Fixed by two rows in `review/corrections.csv` that restore the printed amounts. If CTHRU does this
again in later years, it should become a rule in `combine.annual_rows`. **7061-0033** in FY2025:
CTHRU has $1,452,605 against $1,450,000 printed, with no supplement behind the $2,605; the CTHRU
figure stays (CTHRU first) and the row is flagged `cthru_mismatch`. Unexplained, small.

## Supplemental differences from CTHRU, FY2021–FY2025 (Q28)

*Tierney, 2026-11-21; all 70 laws, CTHRU snapshot 2026-11-12.* What each supplemental difference in
`reports/validation/cthru_mismatches.csv` is. **Fixed:**

- **2022-268 §2A: 1599-0122 and 1599-1214.** The law's web page runs one item into the next ("of the
  total $20,000,000 1599-1214 For a reserve …", no line break and no dotted leader), so the reader
  gave 1599-0122 the $14,000,000 of 1599-1214 and missed 1599-1214. It is the only such run-in in all
  70 laws. Fixed once: 1599-1214 is a row in `config/manual_rows.csv` ($14,000,000, General Fund as
  CTHRU books it, counted), and `review/corrections.csv` gives 1599-0122 its $20,000,000 (federal,
  not counted). `validate` still lists 1599-0122, because it reads the funding actions before
  corrections.
- **Transfers into a trust fund in supplementals no longer count** (decided by Tierney; the Q2/Q15
  rule the GAAs' §2E already follow): 1595-4514 Pension Liability Fund ($100,000,000, 2023-77), and
  in 2025: 1595-0604 ($50,000,000), 1595-6153 ($12,500,000), 1595-0605 ($10,000,000), 1595-1779
  ($1,000,000). In code (`combine.transfers_into_a_fund`). Transfers to the MBTA, and to MassDOT's
  Massachusetts Transportation Trust Fund for a named program (2025-7 §2A, 7 items), are spending
  and still count. CTHRU lists none of the five, so 1595-4514 stays on the comparison list.
- **2023-77 §2 4190-0400 and 4190-0401** (Soldiers' Home in Holyoke, "Consolidated Appropriations
  Act" $708,240 and "American Rescue Plan Act" $1,714,016) add to items the FY2023 GAA appropriates
  as §2D federal grants, so they are federal and don't count (in code). CTHRU carries no §2D items.

**Explained, no change:**

- **1599-9817, FY2022 ($300,000,000).** CTHRU books 2021-102 §61's $300,000,000 as `original`, and
  2022-42 §2's $346,056,813 as `supplemental`; we have both as supplemental rows. Same total, different
  column (also `combine_problems.csv`).
- **1599-0514 ($175,000,000): FY2024 here, FY2025 in CTHRU.** 2024-88 §25 lets the comptroller transfer
  up to $175,000,000 from the Transitional Escrow Fund into this 2023-77 item "following written
  determination" that it is needed, and names no fiscal year. The row takes the item's year (FY2024);
  CTHRU books it when the money moved (FY2025). Same money, different year.
- **1599-6063 (+$100,000) and 1599-6072 (+$1,000,000), FY2022.** 2022-268 §2A ARPA items whose CTHRU
  amounts differ from the printed ones, with no amendment in our laws that explains it. Federal
  money, not counted, so no total changes.
- **2000-0100 (+$100,000) and 2310-0200 (−$100,000), FY2022.** CTHRU shows $100,000 moved from 2310-0200
  to 2000-0100; 2021-76 §11–§14 change both items, and `read_amendments` reads them as wording
  changes with no money. Net zero. For C (`read_amendments`) to check whether §12–§14 move the
  money.
- **7008-1117, FY2023 (CTHRU $200,000).** A 2019-142 §2A item whose end date later laws extended
  (`REAUTH` rows, not counted). CTHRU books the carried-over balance as `supplemental`.
- **2300-0100 and 7008-1116 (FY2023), 4512-0205, 8324-0050 and 1599-0026 (FY2024).** Explained
  above (Q29) and by Emily H. ("Amendment increases CTHRU doesn't show").
- **3000-7040, 4590-0913, 8100-0012, FY2021 ($2,564,373).** Supplementals to FY2021 items that CTHRU's
  FY2021 data doesn't show; FY2021's budget is outside the window. Not yet looked at.
- **FY2026: 48 items ($1,710,130,666) CTHRU has and we don't.** Supplementals approved in 2026, after
  the window (`approved_to` 2025-12-31). A known limitation, not an error.

## The 8 borrowing limits whose items don't add up to them (Q11)

*Tierney, 2026-11-21; `reports/validation/bond_totals.csv` (§13 check 7), all 70 laws.* 39 of 47
in-scope borrowing limits equal the total of their items. The other 8, by cause:

| Limit | Items vs limit | Why |
|---|---|---|
| 2020-383 §32 (§2) | $4,400,000,000 vs $880,000,000 | The law identifies the $3,520,000,000 difference as the federal share (`federal_split = identified`); the capital total leaves it out (§10, New 1). |
| 2022-176 §41 (§2) | $2,812,457,157 vs $611,800,000 | Same: identified federal share of $2,200,657,157. |
| 2022-176 §47 (§2G) | $3,500,000,000 vs $1,750,000,000 | Same: identified federal share of $1,750,000,000. |
| 2020-383 §35 (§2D) | $760,000,000 vs $790,000,000 | **Veto.** The Governor reduced 6621-2117 from $400,000,000 to $370,000,000; the limit kept the passed figure. |
| 2020-383 §38 (§2G) | $450,000,000 vs $700,000,000 | **Pocket veto** of 6720-2127 (Allston Multimodal Project, $250,000,000). |
| 2020-383 §40 (§2I) | $2,165,698,500 vs $2,190,698,500 | **Pocket veto** of 6921-2110 (transportation management association grants, $25,000,000). |
| 2022-176 §48 (§2H) | $25,501,000 vs $8,300,000 | **Unexplained by the law.** One item, 6622-2214 (mobility assistance, intercity bus); it allows Infrastructure Investment and Jobs Act projects but states no federal share. |
| 2024-139 §4 (§2A, §2B) | $1,455,000,000 vs $1,055,000,000 | **Unexplained by the law.** Five of the six items say federal reimbursements may come in, but none states an amount, and there are no vetoes. |

Decision (Tierney): the Q11 rule stands. The capital total keeps the items' amounts and each gap is
flagged (the capital file's "Limit difference note"). The veto and federal-share gaps need nothing
more. The two unexplained gaps ($17,201,000 and $400,000,000) are a known limitation for the
codebook: the law authorizes more spending than borrowing and doesn't say how the rest is paid
(possibly federal reimbursement, or items meant to overlap; §1 of each law lets amounts be shifted
between projects). Their federal split stays `unknown` (the federal-money task's part 2).

## The 20 amendment changes sent to a person (Q21, Q27)

*Tierney, 2026-11-21; `reports/validation/amendment_amounts.csv`, `review = true`, in-scope laws.*
Each was read against the law and the item it changes. The program counts each $0, and that is right:

- **Caps or earmarks inside the item (`in_item_text`), not its total:** the Cambridge Health Alliance
  payment cap in 1595-1068 (2021-29 §48, 2022-42 §42, 2024-206 §42, 2024-248 §127, 2025-14 §84);
  1599-2026's earmark for the Behavioral Health Trust Fund (2022-42 §46, and 2022-268 §221, read
  since reader 0.12.0); 1410-0250's Habitat earmark (2023-28 §67); the treasurer's administration cap
  in 0610-2000 (2023-77 §175, 2024-248 §119); 0321-1510's cap (2025-73 §163).
- **The same law's §2 adds the same money (`match` + Q27 note):** 1595-1068 (2021-29 §49), 3000-7040
  (2023-77 §81), 1775-0700 and 8100-0102 (2024-206 §33, §39), 4513-1012, 4590-0912 and 8100-0006
  (2025-14 §63, §64, §66). Each has its own §2 `INC` row of that amount.
- **The item already shows the new figure (`already_new`):** 2310-0200 (2022-268 §234) and 7006-0071
  (2024-248 §86).

**One was wrong and is fixed:** 2021-76 §12 raises 2000-0100 by $100,000, but was matched with the
same law's §2CI row for 2000-0100 ($100,000), a balance carried forward, not money added. §11–§14
move a $100,000 earmark for the New England Wildlife Center from 2310-0200 to 2000-0100; §14 printed
the struck figure without "$", so it was read as a wording change. Both fixed in code; the two items
now match CTHRU's FY2022 supplementals, and the total is unchanged (+$100,000, −$100,000).

These 20 stay in the review queue until a person can mark items explained (task list).

## Random-row review, rows 101–200

*Tierney, 2026-11-22; Mario's sample `random_review_sample_final 2.0.xlsx` (200 rows, drawn from
`main` on 2026-11-21; the 100 rows matched the 2026-11-22 file exactly).* Each row was checked
against the law text (and CTHRU, where it supplies the amount): amount, funding action, whether it
counts, agency, purpose and policy area. **93 match.** The 7 that don't, and what was done:

| Row | Record | Problem | Fix |
|---|---|---|---|
| 103 | 2023-028-S2D-7004-2030-ORIG-1 | Agency "Office of the Secretary" (the heading) | `label.agency_office`: a bare "Office of the Secretary" takes the line's CTHRU department (49 rows) |
| 181 | 2025-009-S2D-6642-0049-ORIG-1 | Agency "Transportation" (the secretariat heading) | `DEPARTMENT_NAME_FIXES`: Massachusetts Department of Transportation (14 rows) |
| 118 | 2023-077-S2CI-2511-0103-PAC-1 | Policy area for cannabis and hemp *agricultural* oversight | Catalog: Environment and natural resources (7 rows) |
| 176, 177 | 2025-009-S2D-0640-9716/9718-ORIG-1 | Cultural Council arts grants under Government administration (the Lottery's 0640 prefix) | Catalog: the Council's 9 items are Arts, culture, and recreation (22 rows) |
| 149 | 2024-206-S2-1599-6073-INC-1 | VOCA Bridge +$20,000,000 marked federal because CTHRU books the item to the ARPA fund; the reviewer judges this increase state money | Corrections: counts, $20,000,000 |
| 160 | 2024-248-S86-7006-0071-RED-1 | A real −$25,000 counted $0: FY2024's override restored the item to $3,332,411, but the check compared against the post-veto printed $3,307,411 (Q30) | Correction: −$25,000 |

The filled-in rows (Matches / What is wrong / Reviewer / Date) went back to Mario for the shared sheet.

## How the data was made: notes moved from the Status Board
Moved from DESIGN §21 when the Status Board was retired, 2026-11-18. Facts about how parts of the
dataset were built that aren't recorded elsewhere; counts are as of the date given.

- **Policy-area catalog** (`config/line_item_catalog.csv`, Emily R., 2026-11-07): 1,173 line items at
  first. 259 lines from mixed departments and flagged exceptions were decided by hand; 914 were
  generated from the department table and marked `department list (automatic)`. A random 46 of those
  (5%) were spot-checked and 2 changed (7008-0250 → Arts; 2511-0103 → Government administration); 18
  more changed after Emma's review (14 jail addiction-treatment lines → Health; 3 elder housing lines
  and 7503-0101 → Housing), leaving 850 marked automatic. 124 1599 reserves are `label_every_year`.
  The 2026-11-12 review decided 89 more lines by hand (72 operating lines in mixed departments or with
  no CTHRU department, mostly §2D federal grants; 17 bond items), for 1,262 in all.
- **Labels on real data** (2026-11-12): 8,307 rows; policy area from the catalog 5,240, the department
  2,704, a rule 45; all 318 rows left were 1599 reserves, each decided by Emily R. in
  `review/corrections.csv`. 10 reserve lines (17 rows) differ from the catalog's usual area because
  1599 numbers are reused for other purposes (e.g. 1599-1778: senior housing, not a reentry program).
- **Agency fix** (PR #65, 2026-11-12): headings shown in capitals only by the web page's styling were
  missed, so 142 rows had the agency printed above them; fixed in `paragraphs.py`. No amount, total,
  row count or policy area changed. Two misprinted headings in the laws ("XECUTIVE" in 2024-140,
  "ENVIROMENTAL" in 2022-126) are fixed by 12 rows in `review/corrections.csv`.
- **`config/funds.csv`** (2026-11-02): 24 funds with CTHRU fund numbers; 5 federal (General Federal
  Grants, Federal COVID-19 Response, Coronavirus Relief, and the ARPA-filled Broadband Innovation and
  Behavioral Health trust funds), per the partner's Q1 rule.
- **Law list review** (Emma, 2026-11-03): all 52 rows then on the list reviewed; each law's note is in
  the `notes` column of `config/law_list.csv`.
- **Hand-checked expected rows** (`tests/samples/expected/`): 14 amendment rows from 2023-77, 2021-35
  and 2023-15 (Emily H., 2026-11-08); 18 item rows from 2025-3, 2023-77, 2023-28 and 2024-140
  (Tierney); all 16 bond-sample line items checked against the official text (Emma, 2026-10-29).
- **Bond laws** (2026-11-06): on all downloaded bond laws, 191 items and 47 borrowing limits, 0 unread;
  identified federal shares $7,470,657,157 (2020-383 §32, 2022-176 §41 and §47); the split is `unknown`
  for 2020-383 §34, 2021-15 §6, 2022-176 §48 and 2024-139 §4. 2020-383 totals $16,229,698,500 after
  leaving out its 2 pocket-vetoed items.
- **Amendments** (Emily H.): every `read_amendments` row on the six samples was checked against the law
  text (2026-11-04). On all 58 law-list laws (2026-11-08), the struck-figure check found no mismatches.
- **Annual rows** (2026-11-11): the rows equal CTHRU's total `original_enacted` to the dollar for FY2023
  to FY2026; FY2022 is $300,000,000 lower because 1599-9817 is counted once, through 2021-102 §61.
