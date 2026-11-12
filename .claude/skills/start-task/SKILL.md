---
name: start-task
description: Start a task on the appropriations dataset. Gets the latest main (or picks up a branch already in progress), merges finished pull requests, fixes out-of-date docs on main, agrees on the task that matters most, checks nobody is already doing it, and makes a branch. Use only when a student asks what to work on or says they want to begin a new task, not for questions or small requests.
---

# Start a task

The student wants to start useful work quickly. Keep each step's report to a few plain sentences (see "Who you're working with" in CLAUDE.md). The goal and deadlines in CLAUDE.md decide what matters most.

If the student named a task ($ARGUMENTS), steps 1–4 still come first; you deal with the task in step 5.

## 1. Get the latest main, or pick up work in progress
- If there are uncommitted changes, or the session is on a branch other than `main`, say in plain words what's there. Ask whether the student wants to **continue that work** or **start something new**. Never throw work away without a yes.
- **Continuing:** if there are uncommitted changes, commit them on their branch first (with the student's yes), so switching branches is safe. Still do steps 2–3 on `main`, so the docs stay current. Then switch back to the branch, bring in the latest `main`, remind the student what the branch was for, and go to step 7's plan. If bringing in `main` causes a conflict, stop and explain it (WORKFLOW §7). Don't pick a side yourself.
- **Starting new**, or already on a clean `main`: switch to `main` and pull.

## 2. Merge finished work
- List open pull requests (`gh pr list`) and branches that aren't merged yet (`git branch -r --no-merged origin/main`).
- Give one line for each: what it does in plain words, and whether GitHub's automatic checks (CI) pass.
- Finished work sitting in an open pull request helps nobody (WORKFLOW Step 2). Offer to merge each one whose checks pass, one at a time, with the student's yes for each. A quick look first is optional. If one has a problem, offer to fix it and merge it. If a merge causes a conflict, stop and explain it (WORKFLOW §7).
- Pull again after merging.

## 3. Make sure main describes itself accurately
This is WORKFLOW Step 3. `main` now holds everyone's merged work, and its docs should say so before anyone plans from them.
- Compare these with what's actually on `main`:
  - the deadlines in CLAUDE.md (any that have passed?)
  - the milestone tracker (`docs/OVERVIEW.md` §5)
  - the Status Board (DESIGN §21)
  - the Open Questions (§19)
  - `docs/RUNBOOK.md`
  - the to-do items on GitHub (`gh issue list`)
- List anything out of date in a few plain lines, with the fix you suggest. If nothing is, say so in one line and move on.
- If the student agrees, make the docs-only fixes on `main`, show them, and commit and push to `main` once the student says yes.

## 4. Find what matters most
- Read the deadlines in CLAUDE.md, the milestone tracker and the Status Board.
- The earliest unfinished milestone comes first. Close to a deadline, getting the main file out end to end beats everything else.

## 5. Agree on one task
- **If the student named a task:** say whether it serves the goal now (a re-runnable program, shown by the file it produces; see CLAUDE.md). If it belongs to a later milestone while an earlier one is open, say so kindly and suggest the higher-priority task. The student decides.
- **If not:** recommend one software task (never the report, one-pager or presentations; see CLAUDE.md), not a menu, in a few sentences:
  - what it is
  - how it serves the goal (one sentence): a more complete or correct file, or a program that's easier for someone else to run
  - rough size (it should fit in a day or less, or be split)

  If the student has a different idea, take it seriously.

## 6. Check the chosen task isn't already being done
Once a task is agreed, compare it with the pull requests and branches from step 2, recent commits on `main` and the Status Board notes.
- If it overlaps, say where. Suggest building on that work instead of starting again.
- Point out any handoff notes a teammate left for it.
- After the first draft, the re-run is built as you go (CLAUDE.md). If the task touches a stage, check the M6 row of the Status Board for re-run to-dos about that stage, and point out any the task could cover with little extra work.

## 7. Make the branch and plan
- Once the student agrees, make a branch from `main` named with a workstream letter and a few words, e.g. `c/interim-budgets`. Use the letter of the part of the project the task is in. Anyone can work on anything.
- Read the DESIGN sections for the task. Propose a short plan and say what you'll change. Don't edit files until the student says go, and suggest Plan mode for this if they aren't in it.
- Remind them that `/finish-task` checks, commits and shares the work when they're done.
