---
name: start-task
description: Start a task on the appropriations dataset. Gets the latest main (or picks up a branch already in progress), merges finished pull requests, fixes out-of-date docs on main, picks the most pressing task from the finishing plan (OVERVIEW §5), checks nobody is already doing it, and makes a branch. Use only when a student asks what to work on or says they want to begin a new task, not for questions or small requests.
---

# Start a task

The student wants to start useful work quickly. Keep each step's report to a few plain sentences (see "Who you're working with" in CLAUDE.md). The goal and deadlines in CLAUDE.md decide what matters most.

If the student named a task ($ARGUMENTS), steps 1–4 still come first; you deal with the task in step 5.

## 1. Get the latest main, or pick up work in progress
- If there are uncommitted changes, or the session is on a branch other than `main`, say in plain words what's there. Ask whether the student wants to **continue that work** or **start something new**. Never throw work away without a yes.
- **Continuing:** if there are uncommitted changes, commit them on their branch first (with the student's yes), so switching branches is safe. Still do steps 2–3 on `main`, so the docs stay current. Then switch back to the branch, bring in the latest `main`, remind the student what the branch was for, and go to step 7's plan. If bringing in `main` causes a conflict, stop and explain it (WORKFLOW §7). Don't pick a side yourself.
- **Starting new**, or already on a clean `main`: switch to `main` and pull.
- If the student wants to continue work that's in an open pull request but not on this computer (`/finish-task` switches back to `main`), check out that pull request's branch from GitHub and treat it as continuing.

## 2. Merge finished work
- List open pull requests (`gh pr list`) and branches that aren't merged yet (`git branch -r --no-merged origin/main`).
- Give one line for each: what it does in plain words, and whether GitHub's automatic checks (CI) pass.
- Finished work sitting in an open pull request helps nobody (WORKFLOW Step 2). Offer to merge each one whose checks pass, one at a time, with the student's yes for each. A quick look first is optional. If one has a problem, offer to fix it and merge it. If a merge causes a conflict, stop and explain it (WORKFLOW §7).
- Merge with `gh pr merge <number> --merge --delete-branch`, so the merged branch is deleted on GitHub and on this computer. A merged branch is no longer needed: its work is on `main`.
- Pull again after merging.
- **Tidy up old branches.** List branches already merged into `main`, on GitHub (`git branch -r --merged origin/main`) and on this computer (`git branch --merged main`), leaving out `main`. If there are any, say how many and offer to delete them. Their work is safely on `main`. Delete them only after the student says yes. Never delete a branch that isn't merged.

## 3. Make sure main describes itself accurately
This is WORKFLOW Step 3. `main` now holds everyone's merged work, and its docs should say so before anyone plans from them.
- Compare these with what's actually on `main`:
  - the deadlines in CLAUDE.md (any that have passed?)
  - the task list and deadline checklists (`docs/OVERVIEW.md` §5)
  - the Open Questions (DESIGN §19)
  - `docs/RUNBOOK.md`
  - the to-do items on GitHub (`gh issue list`)
- List anything out of date in a few plain lines, with the fix you suggest. If nothing is, say so in one line and move on.
- If the student agrees, make the docs-only fixes on `main`, show them, and commit and push to `main` once the student says yes.

## 4. Find what matters most
- Read the deadlines in CLAUDE.md and the deadline checklists and task list in `docs/OVERVIEW.md` §5.
- The nearest deadline's unfinished items come first: the 4 Dec list (reliable data) before the 11 Dec list (re-run and documentation).

## 5. Agree on one task
- **If the student named a task:** say whether it serves the goal now (see CLAUDE.md). If it belongs to a later deadline while an earlier one's items are open, say so kindly and suggest the more pressing task. The student decides.
- **If not:** recommend the most pressing task from the task list that nobody is on, whoever is asking. Never steer a student toward an area because of who they are or what they did before, and don't try to balance work between people (CLAUDE.md). Recommend one software task (never the report, one-pager, presentation or charts; see CLAUDE.md), not a menu, in a few sentences:
  - what it is
  - how it serves the goal (one sentence): a more complete, correct or easier-to-use file, or a program that's easier for someone else to run
  - rough size (it should fit in a day or less, or be split)

  If the student has a different idea, take it seriously.
- **Within a deadline, impact decides.** Prefer the task that moves the most rows or dollars in the file, judged from the program's output. Don't recommend work on a worry that has no instance in the data (CLAUDE.md, "Ambiguities").

## 6. Check the chosen task isn't already being done
Once a task is agreed, compare it with the task list's "Who's on it" column, the pull requests and branches from step 2, and recent commits on `main`.
- If it overlaps, say where. Suggest building on that work instead of starting again.
- Point out the notes a teammate left for it in the task list.
- If the task touches a stage, check the task list's "Re-run and documentation" rows for anything about that stage the task could cover with little extra work.

## 7. Make the branch and plan
- **Claim the task where everyone can see it.** With the student's yes, put their name in the task's "Who's on it" cell in `docs/OVERVIEW.md` §5, mark it ◐, and commit and push that one-line change straight to `main` (a docs-only fix, CLAUDE.md). A claim on a branch nobody else has yet doesn't stop two people doing the same task.
- Then make a branch from the updated `main`, named for the kind of work plus a few words: `check/`, `edge/`, `sheet/`, `rerun/` or `docs/`, e.g. `check/random-review`.
- Read the DESIGN sections for the task. Propose a short plan and say what you'll change. Don't edit files until the student says go, and suggest Plan mode for this if they aren't in it.
- Remind them that `/finish-task` checks, commits and shares the work when they're done.
