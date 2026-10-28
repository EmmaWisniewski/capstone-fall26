# CLAUDE.md

This repo builds a line-item dataset of Massachusetts state appropriations from laws enacted in calendar years 2021–2025. A 5-person capstone group works on it alongside Claude sessions.

## Read first
- **`docs/DESIGN.md` is the source of truth.** It covers scope, architecture, file contracts (§7), vocabularies (§9), counting rules (§10), workstreams (§16), milestones (§17), open questions (§19), the decision log (§20) and the status board (§21). Read §1–§6 before writing code, and the sections relevant to your task before changing anything.
- Reference inputs live at the repo root: `exampledata.csv` (target export format), `policyareas.csv` (controlled policy areas), `URLs.csv` (starter links).

## Rules
- **Stages talk only through the file contracts in DESIGN §7.** Don't add, rename or retype columns, or add enum values, without updating §7/§9 and `src/ma_approps/schemas.py` and adding a Decision Log entry.
- **Record IDs are stable and deterministic (§9.6).** Never renumber them. Human review depends on them.
- **Never hand-edit generated CSVs** (`data/interim/`, `data/output/`, `review/review_queue.csv`, `reports/`). Record policy-area decisions in `config/line_item_catalog.csv`, one-row fixes in `review/overrides.csv`, and longer reasoning in `review/research_log.md`.
- **Scope filters on the approval date** (`ApprovedDate` 2021-01-01 → 2025-12-31), not on the Acts volume year.
- **CTHRU first (§3.4).** GAA amounts and agencies come from CTHRU; law text is read only for what CTHRU lacks. Inline veto markup is a hint, not truth (§11.4).
- **Automate, don't hand-annotate.** Every routine kind of law is read by code; `config/manual_rows.csv` is an escape hatch only. Nothing may be hard-coded to 2021–2025: future cohorts re-run the program each year (§1).
- **Use `amount_kind` and `additive` for every ledger row.** Interim budgets, ISF chargebacks, reauthorizations, transfers and bond authorizations are not summed into the operating totals (§10).
- **Federal money stays in the data but is flagged**, pending the Office of the State Auditor partner (Q1).
- Be polite to malegislature.gov: about 1 request per second, cache in `data/raw/`, and use offline fixtures in tests.
- Never commit `data/raw/` or API keys. The pipeline uses no LLM (DESIGN §12); don't add one without a Decision Log entry.

## Before saying a stage is done
- Run `pytest`. The golden test (DESIGN §17) and the fixture tests must pass.
- Run `python -m ma_approps validate`. The `unparsed_*` reports must be empty or explained, and CTHRU mismatches must be explained or flagged.
- Update the Status Board (§21), and the Open Questions (§19) and Decision Log (§20) if anything was decided. If a milestone or workstream changed state, also update the high-level tracker in `docs/OVERVIEW.md` §5.

## Who you're working with
- You'll usually be talking to one of the five group members, who are **Master of Public Policy students with very little software development experience**. They use the Claude Code desktop app and usually ask you to run git for them (see `docs/WORKFLOW.md`).
- Explain unfamiliar terms (git, Python, CSV, tests) in plain language without being asked, and check understanding before multi-step changes. Point newcomers to `docs/OVERVIEW.md`.
- Prefer the simplest design that works. Don't add files, settings or abstractions nobody asked for.
- They are the domain experts on policy, budgets and the project's goals. They've been taught "two flavours of confusion" (`docs/WORKFLOW.md`): either Claude used jargon they don't know (slow down and give context), or Claude's plan conflicts with what they know about the data or goals. When they raise the second kind, re-examine the plan; don't defend it.
