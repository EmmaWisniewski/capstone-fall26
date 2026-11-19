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
- If some changes aren't part of this task, say so and offer to leave them out (changes from steps 2–3 belong in it). Small, single-purpose pull requests are easier for teammates to follow.
- If you're on `main`, make a branch first (the kind of work plus a few words, e.g. `check/random-review`).

## 2. No new hand steps for the analyst
Next year an analyst at the State Auditor's office, who isn't a programmer and won't have Claude Code, clones the repo and follows the runbook (CLAUDE.md). Check whether this change adds anything they'd have to do by hand each year, such as:
- editing code
- editing settings that could be worked out automatically
- using Claude Code
- extra steps or commands beyond what the runbook already asks
- making a judgement the runbook doesn't explain

If it does, say so plainly. Then either automate the step in this pull request (if it's small) or add it to the runbook (step 3). If neither fits now, add a row to the "Re-run and documentation" table of the task list (`docs/OVERVIEW.md` §5). If this change finishes one of those rows, mark it ☑.

## 3. Update the docs, in this pull request
The docs should change in the same pull request as the work they describe, so `main` never claims something that hasn't arrived yet.

**Handoff notes for this task.** Teammates will pick up where this left off, and there are no sign-offs to catch gaps. Make sure the docs tell the next person:
- **The task's row in the task list** (`docs/OVERVIEW.md` §5): its status, and notes saying what's done, what's left and anything surprising. Add a row for any new task this work turned up, and tick any deadline checklist item it finishes.
- **Decision Log** (DESIGN §20) and **Open Questions** (§19) if anything was decided or newly asked. Record decisions as decided, not "pending sign-off", and make each one durable: say what rule the code now follows (or which fix-file row handles a one-off), so next year's run needs no one to decide it again. Add an open question only if it has an instance in the data and changes the file (CLAUDE.md, "Ambiguities").
- **`docs/RUNBOOK.md`** if the steps to run a stage changed.
- If the work affects a piece a teammate will pick up, say plainly what they need to know.

**Every doc this change affects.** (`/start-task` already checked that `main`'s docs were current, so look only at what this change touches.) Go through the diff (the list of changed lines) and check each doc that describes something it changed:
- file formats or allowed values: DESIGN §7/§9 and `schemas.py`
- export columns, allowed values, counting rules or flags: `docs/CODEBOOK.md` (once it exists)
- counting rules (§10) or parsing patterns (§11)
- how to run a stage, or setup: README and `docs/RUNBOOK.md`
- how the program works, in plain words: `docs/OVERVIEW.md`
- the to-do items on GitHub (`gh issue list`): if this pull request finishes one, note it for the description (step 6) so it closes on merge

List any doc that still describes the old behaviour, and fix it in this pull request. If everything is covered, say so in one line.

Keep the notes short. They are for a busy classmate, not a report.

## 4. Run the checks
Run the same automatic checks GitHub runs (CI): `ruff check .`, `pytest` and `python -m ma_approps validate`. They come after steps 2–3 so they cover any code or `schemas.py` changes made there.
- If something fails because of this task, explain it in plain words and fix it.
- If it failed before this task too, say so and don't fix it here unless the student wants that.
- If `python -m ma_approps` says "No module named ma_approps", run `chflags -R nohidden .venv` and try again.

## 5. Commit
Show the final file list and a one-line commit message, and get the student's yes. Then commit.

## 6. Push and open the pull request
- Push the branch and open a pull request with `gh pr create`. Don't request reviewers.
- Description, in plain words:
  - what changed
  - how it serves the goal: a more complete or correct file, or an easier re-run
  - any new hand step it added to the runbook or to the task list's "Re-run and documentation" rows
  - what's left or what a teammate needs to know
  - any docs fixed along the way, and `Closes #N` for any to-do item it finishes
  - the check results
- If `gh` asks to log in, the student runs `gh auth login` in the Terminal app (WORKFLOW §7).

## 7. Back to main
Switch this computer back to `main` and pull, so the next session starts clean. The branch stays on GitHub with the pull request. Don't delete it yet: if the pull request needs a fix, the work is on it.
- **If the student merges the pull request now,** for example once the checks pass, delete the branch on GitHub and on this computer: it's no longer needed. (`gh pr merge <number> --merge --delete-branch` does both, and GitHub's merge page also has a delete button.)
- Otherwise, the next `/start-task` merges it and deletes the branch.

## 8. Wrap up
Give a one-line recap, with the pull request link. Suggest starting a fresh session with `/start-task` for the next task.
