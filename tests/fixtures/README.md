# Test fixtures

Offline inputs for tests and CI (DESIGN §15). Layout mirrors `data/raw/`.

| File | Law | Why |
|---|---|---|
| `sessionlaws/2023/28.json` | FY2024 GAA | EX-001…003; veto variants; fund splits; retained revenue |
| `sessionlaws/2023/77.json` | FY2023 closeout | EX-004 (§178); figure changes; date extensions; text-only changes |
| `sessionlaws/2024/140.json` | FY2025 GAA | missing veto markup |
| `sessionlaws/2025/3.json` | FY2025 supp. | short title, trailing period on amount |
| `sessionlaws/2021/35.json` | policy act | whole-item replacement of 2019 ch. 5 item 8100-1014 |
| `sessionlaws/2023/15.json` | FY2024 interim | interim lump sum |

Each file is the full, untrimmed chapter record from `GET /api/SessionLaws/{year}`
(fetched 2026-10-21), written with sorted keys. In that list response the `Year` field is the
**approval** year (2020 ch. 358 shows `Year: 2021`); the Acts volume is the year requested.

`expected/golden.csv` holds the parser- and assemble-derived fields for EX-001…EX-004
(DESIGN §17). Expected rows for the other fixture laws are still to be written by
workstreams B and C.
