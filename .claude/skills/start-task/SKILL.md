---
name: start-task
description: Start a work session on the appropriations dataset. Gets the latest main, checks open pull requests and branches for work that's already under way, finds the task that most moves the final file forward, and makes a branch. Use when a student starts a session, asks what to work on, or names a new task.
---

# Start a task

The student wants to start useful work quickly. Keep each step's report to a few plain sentences (see "Who you're working with" in CLAUDE.md). The goal and deadlines in CLAUDE.md decide what matters most.

If the student named a task ($ARGUMENTS), keep it in mind through every step.

## 1. Get the latest main
- Check that this is a local session (the files in `data/raw/` should exist). If it isn't, say so and stop.
- If there are uncommitted changes or the session is on another branch, say what's there and ask what to do with them before you switch. Never throw work away without a yes.
- Switch to `main` and pull.

## 2. Look at work already under way
- List open pull requests (`gh pr list`) and branches that aren't merged yet (`git branch -r --no-merged origin/main`).
- Give one line for each: what it does in plain words, and whether CI is green.
- Finished work sitting in an open pull request helps nobody (WORKFLOW Step 2). Offer to review and merge any open pull requests first, one at a time, with the student's yes for each. If one has a problem, offer to fix it and merge it.

## 3. Find what matters most
- Read the deadlines in CLAUDE.md, the milestone tracker in `docs/OVERVIEW.md` §5 and the Status Board (DESIGN §21).
- The earliest unfinished milestone comes first. Close to a deadline, getting the main file out end to end beats everything else.

## 4. Check the student's task, if they named one
- **Is it already being done?** Compare it with the pull requests and branches from step 2 and with recent commits on `main`. If it overlaps, say where. Then suggest building on that work instead of starting again.
- **Does it move the final file forward now?** If it belongs to a later milestone while an earlier one is open, say so kindly and suggest the higher-priority task. The student decides.

## 5. Recommend one task
In a few sentences:
- what the task is
- how it moves the final file forward (one sentence)
- what's already there: Status Board notes, handoff notes, related pull requests
- rough size (it should fit in a day or less, or be split)

Recommend one task, not a menu. If the student has a different idea, take it seriously.

## 6. Make the branch and plan
- Once the student agrees, make a branch from `main` named with their workstream letter and a few words, e.g. `c/interim-budgets`. Use the letter of the part of the project the task is in. Anyone can work on anything.
- Read the DESIGN sections for the task. Propose a short plan and say what you'll change. Don't edit files until the student says go, and suggest Plan mode for this if they aren't in it.
- Remind them that `/finish-task` checks, commits and shares the work when they're done.
