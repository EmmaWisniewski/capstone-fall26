# CLAUDE.md

This repo builds a line-item dataset of Massachusetts state appropriations from laws approved in calendar years 2021–2025, for the Office of the State Auditor. It is a Master of Public Policy capstone: five students working with Claude sessions over one semester.

## The goal and the deadlines
- **The goal is a program anyone can re-run with trivial effort.** That includes someone at the State Auditor's office who isn't a programmer. They add each new year's laws by running **one command in the terminal** and working through the short review checklist in `docs/RUNBOOK.md` (milestone M6). They won't have Claude Code, so nothing in the re-run or the runbook may depend on it.
- **The program's output is the dataset:** `data/output/ma_appropriations_cy{first}_{last}.csv` (named from the scope years in `config/settings.toml`, so `…cy2021_2025.csv` for now), in the `exampledata.csv` format. You can't reach the goal without producing a useful file along the way. The file is also how we know the program works, so getting it out end to end comes first.
- **Every task should do one of two things:** make the program produce a more complete or correct file, or make it easier for someone else to run. Before proposing work, say in one sentence how it does; if you can't, don't propose it.
- **"Trivial to re-run" means fewer steps and clearer instructions,** not more settings, options or abstractions. Re-runnability is never a reason for engineering polish.
- **Deadlines** (update these when they pass):
  - **Fri 13 Nov 2026:** first draft of the file goes to the partner. Until then, the only priority is producing it end to end, with gaps flagged rather than fixed.
  - **Fri 4 Dec 2026:** presentation to the State Auditor, with the project about 95% done. That means the re-run nearly works and is documented well enough for the Auditor's office to use, with the file it produces as the evidence. A good file that only its builders could produce is not 95%.
- **Finishing beats perfecting.** Work on the earliest unfinished milestone (`docs/OVERVIEW.md` §5) before polishing later ones. A finished file with flagged rows is better than a perfect file that doesn't exist.
- **Build the re-run as you go, not as a final phase.** The re-run test (M6) is the last milestone, but it can't wait until the end. After the first draft, every change to a stage keeps that stage's runbook step working for someone without Claude Code. The open re-run to-dos are on the M6 row of the Status Board (DESIGN §21).
- **Do what was asked, then stop.** Mention other problems you notice in one line at the end; fix them only if the user says yes. Don't add files, settings or abstractions nobody asked for.

## Who you're working with
- The students are **domain experts in policy and budgets with no real experience of Python or git**. They use the Claude Code desktop app and ask you to run git for them.
- **Pitch every reply to someone who has never programmed.** Lead with what it means for the dataset or their task, in a few sentences. Leave out code, commands, file paths and error text unless they ask. Use the git terms the students have learned (commit, branch, push, pull request, merge) as they are, since they're precise. Explain any other technical term in the same sentence, including "diff" (the list of changed lines) and "CI" (GitHub's automatic checks). Offer one recommended next step, not a menu of options, and check understanding before multi-step changes.
- When a student says your plan doesn't fit what they know about the laws, the data or the goal, re-examine the plan rather than defending it. Point newcomers to `docs/OVERVIEW.md`.
- Lawrence, the library's text mining specialist, is a facilitator and reference person only: not an instructor, supervisor or reviewer.

## How the group works: a student team, not a company
Process built for large companies (required reviews, sign-offs, code owners) slows this group down and confuses it. Instead:
- **Everyone owns everything equally.** Workstream letters (A–E, DESIGN §16) only show where each person started. Anyone may change, fix, merge or decide anything.
- **No sign-offs.** The student you're working with can decide for the group. Record decisions as decided, never "pending X's sign-off". Only questions for the partner (DESIGN §19) wait on someone else.
- **Instead of sign-offs, two habits.** Before starting a task, check open branches and pull requests for the same work. When work affects something a teammate will pick up, leave notes on what was done, what's left and why (Status Board §21, DESIGN, the PR description). The `/start-task` and `/finish-task` commands (`.claude/skills/`) walk through both. Follow the same steps when a student asks in other words.
- **Reviews are optional.** If a pull request has a problem, fix it and merge it rather than sending it back.
- Work in a local session, not the cloud (`data/raw/` exists only locally). Before committing, list the files you'll include. Nothing from `data/`, `reports/` or `review/review_queue.csv`, and no keys. Docs-only fixes may go straight to `main` once the user has seen them and said yes.

## Data rules
`docs/DESIGN.md` is the source of truth. Read §1–§6 and the sections for your task before changing code. `docs/RUNBOOK.md` tells future groups how to add a year. If it disagrees with DESIGN, fix the runbook.
- **Stages talk only through the file formats in DESIGN §7 and the allowed values in §9.** Changing them means updating §7/§9, `src/ma_approps/schemas.py` and the Decision Log (§20).
- **Record IDs never change (§9.6).** Human review depends on them.
- **Never hand-edit generated files** (`data/interim/`, `data/output/`, `review/review_queue.csv`, `reports/`).
- **Automate what recurs; record one-time fixes once.** Code handles any pattern that will recur in future years, because future groups re-run the program each year and nothing may be hard-coded to 2021–2025. A one-time misprint is fixed by adding a row to an existing fix file the program applies on every run: `review/corrections.csv`, `config/item_number_fixes.csv`, `config/citation_fixes.csv`, or `config/manual_rows.csv`. Nothing fixed by hand should need fixing again, and a one-off never needs new code or a new file format.
- Policy areas come only from `policyareas.csv` and are recorded in `config/line_item_catalog.csv`; explanations of unread sections in `review/unread_explanations.csv`; longer reasoning in `review/research_log.md`.
- **Scope is by approval date** (2021-01-01 → 2025-12-31), not the Acts volume year.
- **CTHRU first (§3.4):** annual-budget amounts and agencies come from CTHRU; law text fills only what CTHRU lacks. Veto markup in the text is a hint, not truth (§11.4).
- **Every funding-action row sets `amount_kind` and `counts_toward_total` (§10).** Interim budgets, chargebacks, reauthorizations, transfers and bond authorizations don't count toward operating totals.
- **Federal-source money is kept but flagged and left out of totals;** state surplus counts as state money (Q1, decided by the partner).
- Download from malegislature.gov politely (about 1 request per second, cached in `data/raw/`); tests use offline samples. Never commit `data/raw/` or keys. No LLM in the pipeline (§12).

## Before saying work is done
- Run the same checks as GitHub: `ruff check .`, `pytest` and `python -m ma_approps validate`. Unread sections must be explained, and CTHRU mismatches explained or flagged.
- Update the Status Board (§21), plus the Open Questions (§19) and Decision Log (§20) if anything was decided, `docs/OVERVIEW.md` §5 if a milestone changed, and `docs/RUNBOOK.md` if a stage's steps changed.
