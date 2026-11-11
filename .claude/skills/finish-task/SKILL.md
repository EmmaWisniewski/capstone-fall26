---
name: finish-task
description: Finish a task on the appropriations dataset. Checks the work, makes sure handoff notes and docs are up to date, commits, pushes and opens a pull request.
disable-model-invocation: true
---

# Finish a task

The student wants this work checked, documented for teammates and shared. Keep each step's report to a few plain sentences (see "Who you're working with" in CLAUDE.md).

## 1. Show what changed
- Summarize in plain words what changed and why, and list the files.
- Flag anything that doesn't belong in a commit: files under `data/`, `reports/` or `review/review_queue.csv`, keys or passwords. Leave them out.
- If some changes aren't part of this task, say so and offer to leave them out. Small, single-purpose pull requests are easier for teammates to follow.
- If you're on `main`, make a branch first (letter plus a few words, e.g. `d/bond-policy-areas`).

## 2. Run the checks
Run the same checks as CI: `ruff check .`, `pytest` and `python -m ma_approps validate`.
- If something fails because of this task, explain it in plain words and fix it.
- If it failed before this task too, say so and don't fix it here unless the student wants that.
- If `python -m ma_approps` says "No module named ma_approps", run `chflags -R nohidden .venv` and try again.

## 3. Leave handoff notes
Teammates will pick up where this left off, and there are no sign-offs to catch gaps. Make sure the docs tell the next person:
- **Status Board** (DESIGN §21): this item's row says what's done, what's left and anything surprising.
- **`docs/OVERVIEW.md` §5** if a milestone or workstream changed state.
- **Decision Log** (§20) and **Open Questions** (§19) if anything was decided or newly asked. Record decisions as decided, not "pending sign-off".
- **`docs/RUNBOOK.md`** if the steps to run a stage changed.
- If the work affects a piece a teammate will pick up, say plainly what they need to know.

Keep the notes short. They are for a busy classmate, not a report.

## 4. Commit
Show the final file list and a one-line commit message, and get the student's yes. Then commit.

## 5. Push and open the pull request
- Push the branch and open a pull request with `gh pr create`. Don't request reviewers.
- Description, in plain words:
  - what changed
  - how it moves the final file forward
  - what's left or what a teammate needs to know
  - the check results
- If `gh` asks to log in, the student runs `gh auth login` in the Terminal app (WORKFLOW §7).
- Tell the student they can merge it once CI is green. Otherwise the next `/start-task`, theirs or a classmate's, will offer to.

## 6. Wrap up
Give a one-line recap, with the pull request link. Suggest starting a fresh session with `/start-task` for the next task.
