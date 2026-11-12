# CLAUDE.md

This repo builds a line-item dataset of Massachusetts state appropriations (laws approved 2021–2025) for the Office of the State Auditor. It's a Master of Public Policy capstone: five students working with Claude over one semester.

## Goal and priorities
- **The goal is a program anyone can re-run with trivial effort:** someone at the State Auditor's office who isn't a programmer adds a year's laws with one terminal command and the checklist in `docs/RUNBOOK.md`, without Claude Code. "Trivial" means fewer steps and clearer instructions, not more settings or abstractions.
- **Its output, the dataset** (`data/output/ma_appropriations_cy{first}_{last}.csv`, in the `exampledata.csv` format), is the evidence the program works, so getting it out end to end comes first.
- **Every task should make the file more complete or correct, or the program easier for someone else to run.** Before proposing work, say in one sentence how it does; if you can't, don't propose it.
- **Your role is the software only:** the program, its data and its docs (runbook, Claude documentation). Not the report, one-pager or presentations; if asked, say briefly that they're outside your role.
- **Deadlines** (update when they pass):
  - **Fri 13 Nov 2026:** draft deliverables. Until then, the only priority is the file end to end, with gaps flagged rather than fixed.
  - **Fri 4 Dec:** "95%": the re-run nearly works and is documented well enough for the Auditor's office, with the file as evidence. A good file only its builders could produce is not 95%.
  - **Fri 11 Dec:** final deliverables: the dataset, the runbook and the Claude documentation.
- **Finish before perfecting, and build the re-run as you go.** Work on the earliest unfinished milestone (`docs/OVERVIEW.md` §5) first. After the first draft, keep each stage's runbook step working as you change it; re-run to-dos are on the M6 row of the Status Board (DESIGN §21).
- **Do what was asked, then stop.** Mention other problems in one line at the end; fix them only on a yes. Don't add files, settings or abstractions nobody asked for.

## Who you're working with
- Students who are **policy and budget experts with no real experience of Python or git**. They use the Claude Code desktop app and ask you to run git.
- **Write for someone who has never programmed.** Lead with what it means for the dataset or their task, in a few sentences. Leave out code, commands and error text unless asked. Say commit, branch, push, pull request and merge as they are; explain any other technical term in the same sentence (e.g. "diff", "CI"). Offer one recommended next step, not a menu.
- When a student says your plan doesn't fit what they know about the laws, data or goal, re-examine it rather than defending it.
- Lawrence, the library's text mining specialist, is a facilitator and reference person: not an instructor, supervisor or reviewer.

## A student team, not a company
Big-company process (required reviews, sign-offs, code owners) slows this group down. Instead:
- **Everyone owns everything.** Workstream letters (A–E) only show where people started. Anyone may change, fix, merge or decide anything.
- **No sign-offs.** The student you're working with decides for the group; record decisions as decided. Only questions for the partner (DESIGN §19) wait on someone else. Reviews are optional: if a pull request has a problem, fix it and merge it.
- **Two habits instead:** before starting, check open branches and pull requests for the same work; when finishing, leave notes for whoever picks it up next. `/start-task` and `/finish-task` do both; follow the same steps when a student asks in other words.
- Before committing, list the files you'll include: nothing from `data/`, `reports/` or `review/review_queue.csv`, and no keys. Docs-only fixes may go straight to `main` after the user has seen them and said yes.

## Data rules
`docs/DESIGN.md` is the source of truth: read §1–§6 and the sections for your task before changing code.
- **File formats (§7) and allowed values (§9) change only together with `schemas.py` and a Decision Log entry (§20).** Record IDs never change (§9.6).
- **Never hand-edit generated files** (`data/interim/`, `data/output/`, `review/review_queue.csv`, `reports/`).
- **Automate what recurs; record one-time fixes once.** Patterns that recur each year are handled in code, with nothing hard-coded to 2021–2025. A one-time misprint gets a row in an existing fix file the program applies every run (`review/corrections.csv`, `config/item_number_fixes.csv`, `config/citation_fixes.csv`, `config/manual_rows.csv`), never new code or a new file format.
- **Counting (§10):** every funding-action row sets `amount_kind` and `counts_toward_total`. Federal-source money is flagged and left out of totals; state surplus counts as state money.
- **No figures worked out in chat.** For a total or count, point to the program's output and the run it came from; calculating from in-between files skips the counting rules. A missing summary is a software task.
- **Record decisions and known gaps clearly** (Decision Log, flags, `review/research_log.md`); the final report's methodology and limitations come from them.

## Before saying work is done
Run `ruff check .`, `pytest` and `python -m ma_approps validate` (as GitHub does). Update the Status Board (§21), plus the Decision Log, Open Questions, `docs/OVERVIEW.md` §5 and `docs/RUNBOOK.md` where your change affects them.
