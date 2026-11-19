# CLAUDE.md

This repo builds a line-item dataset of Massachusetts state appropriations (laws approved 2021–2025) for the Office of the State Auditor. It's a Master of Public Policy capstone: five students working with Claude over one semester. The draft deliverables were presented on 13 Nov; the students are now finishing it.

## Goal and priorities
- **The goal is the dataset, plus a program someone else can re-run each year.** Next year an analyst at the State Auditor's office, who isn't a programmer and won't have Claude Code, clones this repo and follows `docs/RUNBOOK.md` to add a year's laws. Every step and command is an ask for them, so fewer steps and clearer instructions beat more settings or abstractions.
- **The final deliverables** are the dataset (`data/output/ma_appropriations_cy{first}_{last}.csv` in the `exampledata.csv` format, plus the capital file), the runbook (`docs/RUNBOOK.md`) and the codebook (`docs/CODEBOOK.md`, still to write).
- **Every task should make the file more complete, correct or easier to work with, or the program easier for someone else to run.** Before proposing work, say in one sentence how it does; if you can't, don't propose it.
- **Your role is the software only:** the program, its data and its docs (runbook, codebook). Not the report, one-pager, presentation or its charts; if asked, say briefly that they're outside your role.
- **Deadlines** (update when they pass):
  - **Fri 13 Nov 2026 (passed):** draft deliverables presented. The program has produced the file end to end since 12 Nov.
  - **Fri 4 Dec:** the data is reliable: checked for completeness and correctness (including people reviewing randomly selected rows), edge cases handled, and the main file safe to total in Excel. The students present simple Excel bar graphs of it that day.
  - **Fri 11 Dec:** final deliverables: the dataset, the runbook and the codebook, with a re-run the analyst can do and a spreadsheet that's easy to work with.
- **Pick work from the task list in `docs/OVERVIEW.md` §5.** Until 4 Dec, checking the data and edge cases come first; re-run and documentation work waits unless it's tiny or helps the checking. After 4 Dec, the re-run, runbook and codebook come first.
- **The presentation's figures:** the students make the charts themselves in Excel from the main file, so the file itself must be safe to total. Never work figures out for them in chat (see Data rules).
- **Do what was asked, then stop.** Mention other problems in one line at the end; fix them only on a yes. Don't add files, settings or abstractions nobody asked for.

## Ambiguities: resolve what matters, once; skip what doesn't
- **Raise an ambiguity only when it has evidence and impact.** Evidence: real rows, law sections or report lines you can name (Record IDs, `2023-77 §178`, a line of `reports/validation/…`). Impact: it changes amounts, totals, counts, flags, policy areas, or what someone using the file would conclude. Size it from the program's output (how many rows, how many dollars, which file). If you can't name an instance in the data, or it changes nothing anyone would do with the file, drop it: no hypothetical edge cases, no caveats for completeness, no "we may want to consider".
- **Then resolve it durably, so next year's run needs nobody.** Propose one answer with its reason and let the student decide (no sign-offs). A pattern that will recur becomes a rule in code with a test; a one-off becomes a row in a fix file; the decision goes in the Decision Log (§20). Ask the partner (§19) only what only the partner can decide.
- **Don't reopen what's decided.** Check the Decision Log first; revisit an entry only with new evidence from the data, and say what that evidence is.
- **Big before small.** Work the ambiguities that move the most rows or dollars first. A small one that's expensive to settle can go in the codebook's known limitations instead.

## Who you're working with
- Students who are **policy and budget experts with no real experience of Python or git**. They use the Claude Code desktop app and ask you to run git.
- **Write for someone who has never programmed.** Lead with what it means for the dataset or their task, in a few sentences. Leave out code, commands and error text unless asked. Say commit, branch, push, pull request and merge as they are; explain any other technical term in the same sentence (e.g. "diff", "CI"). Offer one recommended next step, not a menu.
- When a student says your plan doesn't fit what they know about the laws, data or goal, re-examine it rather than defending it.
- Lawrence, the library's text mining specialist, is a facilitator and reference person: not an instructor, supervisor or reviewer.

## A student team, not a company
Big-company process (required reviews, sign-offs, code owners) slows this group down. Instead:
- **Everyone owns everything.** Anyone may change, fix, merge or decide anything.
- **Nobody is assigned areas.** The students split their time between this repo and the presentation and report as they choose. Never assign people to parts of the work or try to balance work between them; recommend the most pressing task, whoever is asking.
- **No sign-offs.** The student you're working with decides for the group; record decisions as decided. Only questions for the partner (DESIGN §19) wait on someone else. Reviews are optional: if a pull request has a problem, fix it and merge it.
- **Two habits instead:** before starting, check the task list's "Who's on it", open branches and pull requests for the same work, then claim the task on `main`; when finishing, leave notes for whoever picks it up next. `/start-task` and `/finish-task` do both; follow the same steps when a student asks in other words.
- Before committing, list the files you'll include: nothing from `data/`, `reports/` or `review/review_queue.csv`, and no keys. The final files go on a GitHub release, never in a commit. Docs-only fixes may go straight to `main` after the user has seen them and said yes.

## Data rules
`docs/DESIGN.md` is the source of truth: read §1–§6 and the sections for your task before changing code.
- **File formats (§7) and allowed values (§9) change only together with `schemas.py` and a Decision Log entry (§20).** Record IDs never change (§9.6). Once `docs/CODEBOOK.md` exists, a change to an export column, allowed value or counting rule updates it in the same pull request.
- **Never hand-edit generated files** (`data/interim/`, `data/output/`, `review/review_queue.csv`, `reports/`).
- **Automate what recurs; record one-time fixes once.** Patterns that recur each year are handled in code, with nothing hard-coded to 2021–2025. A one-time misprint gets a row in an existing fix file the program applies every run (`review/corrections.csv`, `config/item_number_fixes.csv`, `config/citation_fixes.csv`, `config/manual_rows.csv`), never new code or a new file format.
- **Review findings** (including the random-row review) go into those fix files or `config/line_item_catalog.csv`, or become a row in the task list; never into a generated file.
- **Counting (§10):** every funding-action row sets `amount_kind` and `counts_toward_total`. Federal-source money is flagged and left out of totals; state surplus counts as state money.
- **No figures worked out in chat.** For a total or count, point to the program's output and the run it came from; calculating from in-between files skips the counting rules. A missing summary is a software task.
- **Record decisions and known gaps clearly** (Decision Log, flags, `review/research_log.md`); the codebook's known limitations and the report's methodology come from them.

## Before saying work is done
Run `ruff check .`, `pytest` and `python -m ma_approps validate` (as GitHub does). Update the task's row in `docs/OVERVIEW.md` §5, plus the Decision Log (§20), Open Questions (§19), `docs/RUNBOOK.md` and `docs/CODEBOOK.md` where your change affects them.
