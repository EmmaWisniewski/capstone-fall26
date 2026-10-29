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
(DESIGN §17). Expected rows for the other sample laws are still to be written by
workstreams B and C.
