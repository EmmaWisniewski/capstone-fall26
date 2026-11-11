# Combine and Export: Proposed Work Split

MA Appropriations Capstone · Proposal from Mario, coordinator · 8 November 2026

## Proposal

The reading stages are built and merged. What remains is putting the data together: combine, labels, export and validation, plus law discovery and the runbook. This is the proposed owner for each piece. Each person confirms or changes their own piece, and the group then records the result in the Decision Log ([DESIGN.md §20](DESIGN.md)).

## Who does what

| Piece | What it covers | Owner |
|---|---|---|
| Annual budget rows | Turn CTHRU amounts into "Original appropriation" rows, with veto status and the fee-revenue and chargeback rules | **Mario** |
| Shared core of combine | Give each row its ID, decide what counts toward totals, split by fund, write the combined file | **Everyone** |
| Supplemental rows | Turn supplemental and surplus items from `read_items` into funding rows | **Tierney** |
| §2D federal grant rows | Federal grant items: amounts from the law text, flagged federal, not counted toward totals | **Tierney** |
| Amendment rows and running amounts | Turn changes to earlier laws into rows and connect the running-amounts logic to combine | **Emily H.** |
| Bond rows | Turn bond items into "Capital authorization" rows, linked to their borrowing limits | **Emma** |
| Labels | Agency, purpose, policy area and the yes/no columns on the combined table | **Emily R.** |
| Export: main file | Write the 19-column main spreadsheet | **Mario** |
| Export: capital file | Write the separate bond spreadsheet | **Emma** |
| Validation | CTHRU comparison, bond totals against borrowing limits (check 7), struck-figure check | **Mario** |
| Law discovery | Automatically find new laws each year and add them to the law list as "to be decided" | **Emma** |
| Runbook | Step-by-step guide for future groups to re-run the program; later tested on 2026 laws | **Everyone contributes** |

## Notes

- Each piece of combine hands over rows in the funding actions format ([DESIGN.md §7](DESIGN.md)), so nobody edits anyone else's code.
- **How to plug in your piece** (shared core, Emma, 2026-11-10): write one function `your_rows(inputs, settings)` in `combine.py` and put it in `combine.BUILDERS` next to your piece's name. `inputs` holds every input table as rows (`law_list`, `items_raw`, `bond_items_raw`, `bond_authorizations_raw`, `amendments_raw`, `cthru_line_items`, `funds`, `manual_rows`). Return funding-action rows in source order; leave `record_id` and `counts_toward_total` empty, because the core sets them. For fund splits, add `fund_splits_raw` (from `items_raw`), `fund_numbers` (from CTHRU) or `section_fund_default` to each row; the core turns them into `fund_splits.csv` and sets `fund_primary`, `federal_share` and the federal flags. `combine.bond_rows` is a worked example.
- Suggested order: annual rows and supplemental rows first, because together they produce the four example rows (milestone M1). Amendments and bonds follow. Labels, export and the full checks come after the combined table exists. The runbook comes last.
- Not yet assigned: the extended export file (the main file plus every extra column). It would naturally go with the main file.
- To confirm with the group: who builds the §2D rule, and the veto status "unknown" with the flag `veto_unverified` for those rows.

## For the group meeting

- Sign off milestone M0 (the v0.2 redesign, the file formats, and the two proposals from 21 October).
- Decide the open format questions: Q11, Q12 and Q16 (bond file), Q13 and Q14 (vetoes).
- Agree a start date for combine, and each owner updates their own rows on the status board.
