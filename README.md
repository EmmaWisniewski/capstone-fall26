# Massachusetts appropriations dataset (CY2021–2025)

A line-item dataset of every Massachusetts state appropriation in laws approved
2021-01-01 → 2025-12-31.

**New here? Read these first:**
- [`docs/OVERVIEW.md`](docs/OVERVIEW.md): how the program works, who owns what, and where things stand
- [`docs/WORKFLOW.md`](docs/WORKFLOW.md): working with Claude Code and git (branches, commits, pull requests)
- [`docs/DESIGN.md`](docs/DESIGN.md): the full design and source of truth

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m ma_approps validate
```

If `pytest` passes but `python -m ma_approps` says `No module named ma_approps`, macOS has marked
`.venv` hidden and Python 3.13+ skips hidden `.pth` files. Fix it with `chflags -R nohidden .venv`.

Run stages with `python -m ma_approps run --stage {discover…export|all} [--law 2023-28] [--offline]`.
Unimplemented stages are skipped with a message.

## Where things live

- `config/` — human-curated inputs (`laws_registry.csv`, `manual_rows.csv`, `funds.csv`, `settings.toml`)
- `src/ma_approps/` — one module per stage; `schemas.py` holds every column list and enum
- `tests/fixtures/` — offline copies of the six fixture laws plus golden expected rows
- `review/` — `overrides.csv` and `research_log.md` (the only places to record human decisions)
- `data/raw/` — download cache, never committed

Set `contact_email` in `config/settings.toml` before running `fetch`. The Anthropic key comes
from the `ANTHROPIC_API_KEY` environment variable.
