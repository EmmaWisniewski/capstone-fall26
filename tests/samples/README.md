# Test samples

Offline inputs for tests and CI (DESIGN §15). Layout mirrors `data/raw/`.

| File | Law | Why |
|---|---|---|
| `sessionlaws/2023/28.json` | FY2024 GAA | EX-001…003; veto variants; fund splits; retained revenue |
| `sessionlaws/2023/77.json` | FY2023 closeout | EX-004 (§178); figure changes; date extensions; text-only changes |
| `sessionlaws/2024/140.json` | FY2025 GAA | missing veto markup |
| `sessionlaws/2025/3.json` | FY2025 supp. | short title, trailing period on amount |
| `sessionlaws/2021/35.json` | policy act | whole-item replacement of 2019 ch. 5 item 8100-1014 |
| `sessionlaws/2023/15.json` | FY2024 interim | interim lump sum |
| `sessionlaws/2024/139.json` | IT bond ($1.66B) | bond sample for `read_bonds`: capital sections start at §2A (no §2); §4 authorizes borrowing for two sections (2A and 2B); earmarks inside item text; uneven spacing before amounts |
| `sessionlaws/2025/17.json` | Chapter 90 bond ($1.19B) | Chapter 90 sample: §2 municipal roads ($300M) and §2A MassDOT programs ($885M), each with its own borrowing section; contains a narrow no-break space (U+202F) that text cleaning must handle |

Each file is the full, untrimmed chapter record from `GET /api/SessionLaws/{year}`, written
with sorted keys: the first six fetched 2026-10-21, the two bond samples 2026-10-28 by the `laws`
stage. In that list response the `Year` field is the
**approval** year (2020 ch. 358 shows `Year: 2021`); the Acts volume is the year requested.

`expected/example_rows.csv` holds the parser- and combine-derived fields for EX-001…EX-004
(DESIGN §17). Hand-checked rows from the other sample laws are in
`expected/items_raw_selected.csv` (workstream B) and `expected/amendments_raw_selected.csv`
(workstream C: 14 rows from 2023-77, 2021-35 and 2023-15, one or more of each `action_type` the samples have (none strikes an item),
checked against the law text by Emily H., 2026-11-04 and 2026-11-08).

`expected/bond_items.csv` and `expected/bond_authorizations.csv` hold the expected `read_bonds`
output for the two bond samples (workstream A; DESIGN §11.2 "Bond laws"):
- `bond_items.csv`: every capital-section item, with a subset of the `bond_items_raw` columns.
  All 16 line items were hand-checked against the official text on malegislature.gov
  (Emma, 2026-10-29).
- `bond_authorizations.csv`: each borrowing-limit section, in the format of
  `bond_authorizations_raw.csv` (DESIGN §7.16, decided 2026-11-06), without the reader columns.

`para_start`/`para_end` use the paragraph numbering of `paragraphs.py` (PR #6): 0-based, counting
non-empty paragraphs. `tests/test_law_list_and_samples.py` checks that every ID and amount appears
in the sample's text, and that the items add up to the borrowing limits, except for 2024-139 §4,
whose items exceed it by $400,000,000.
