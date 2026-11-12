# Working with Claude Code and git

A refresher for the "how" of making progress on this project. For what the program does and who started which part, see [`OVERVIEW.md`](OVERVIEW.md).

---

## 1. The mental model

- **The program is the `.py` files** in `src/ma_approps/`. These are text files of
  Python code.
- **Chatting with Claude Code can change those files.** You can edit them yourself too, but if you are in "code" more (rather than the regular "chat" mode), Claude will directly program for you in your copy of these files.
- **Git saves and shares snapshots of the files.** Your edits sit only on your computer until you
  save a snapshot, upload it, and add it to the group's shared version. Teammates see your work
  only after that.

So the loop is: **ask Claude to edit files → check the edits → save a snapshot → share it with the
group.**

---

## 2. What to actually do

### The quick way: two commands
The project has two **commands** (Claude Code calls them "skills"). Each one is a saved set of instructions that tells Claude to work through several of the steps below, in order, so you don't have to type each "Say:" line yourself. They live in the repo (`.claude/skills/`), so everyone gets them once they have the latest `main`.

**How to use one:** in the prompt box, type `/`. A menu of commands appears. Pick one, or keep typing its name, then press Return.

| Command | When | What Claude does with you |
|---|---|---|
| **`/start-task`** | When you want to begin a task, or ask what to work on | Steps 1–6: gets the latest `main`, or picks your unfinished branch back up; offers to merge finished pull requests; checks `main`'s docs are up to date and offers to fix them there; finds the most important unfinished task (or checks the one you name); checks nobody is already doing it; makes a branch and proposes a plan |
| **`/finish-task`** | When the task is done | Steps 7 and 8: shows what changed; checks it doesn't add a yearly hand step for future re-runners; writes handoff notes for teammates and checks every doc your change affects is updated; runs the automatic checks; commits; pushes; opens the pull request |

Good to know:
- **You can name your task after the command,** e.g. `/start-task bond policy areas`. Without one, Claude recommends a task.
- **Claude still asks before anything important.** It waits for your yes before merging a pull request, before starting to edit, and before committing. Each command reports in a few plain sentences at each step, so you can stop it or change direction.
- **`/start-task` may start on its own** if you just ask "what should I work on?". **`/finish-task` only runs when you type it**, so Claude never commits or opens a pull request unless you asked.
- **Two docs checks, one at each end.** `/start-task` makes sure `main`'s docs describe what's actually on `main`, and fixes them there after your yes. `/finish-task` makes sure your change updated every doc it affects. Those updates go in your pull request, so the docs and the work they describe arrive on `main` together.
- **One task per session.** After `/finish-task`, start a fresh session and type `/start-task` again. If you stopped partway through a task, `/start-task` offers to pick your branch back up.
- **If a command isn't in the menu,** you probably don't have the latest `main` yet. Ask Claude to get it, then start a new session.
- **To change what a command does,** ask Claude to edit its instructions in `.claude/skills/start-task/SKILL.md` or `.claude/skills/finish-task/SKILL.md`. They're plain text, like these docs. Share the change the usual way, so everyone gets it.

The steps below explain what the commands do, and how to do each step by hand.

### Step 1: Work locally, and start from the latest `main`
When you start a session in the desktop app, choose **Local**, not a cloud environment. (A cloud
session runs on another computer with its own copy of the project, and your files (like the downloaded laws in `data/raw/`) aren't there
for it. That has caused problems for the group.) If you're not sure which kind of session you're in,
ask Claude: "Are you running locally on my computer or in the cloud?"

Then make sure you're building on everyone's newest work.
> **Say:** "Make sure I'm working on the group's latest version of the project."

### Step 2: Add in your classmates' finished work (merge open pull requests)
When your classmates have finished something, pulling it in to the "main" codebase lets everyone start using it. Leaving these sitting open creates extra work and makes the next steps more complicated than they need to be.
> **Say:** "Are there any open Pull Requests? I want to work through closing all of them."

Then, for each PR:
- **GitHub's automatic checks pass:** merge it. Nobody needs to approve it first. A quick look
  (§5) is optional, if you want to understand what changed.
- **Has a problem** (one you found, or one a teammate pointed out): **fix it yourself, then
  merge it.** Don't send it back to its author and wait. That leaves it open for days and makes
  more work for everyone.
  > **Say:** "Proposed change #12 has a problem: [what's wrong]. Fix it in that change, check that
  > everything still works, and then add it to the group's shared version."

### Step 3: Make sure docs are up to date
> **Say:** "Check whether our project documents still match the work that's been finished: the
> progress tracker, the status board, the open questions, the runbook, and the to-do items on GitHub.
> List anything that's out of date and suggest fixes. Don't change anything yet."

Docs fixes shouldn't wait for a review. Once you agree with the fixes:
> **Say:** "Make these fixes directly in the group's shared version and upload them."

### Step 4: Choose the task that matters most
Pick the next open task that most directly moves us toward the final goal, the released dataset.
> **Say:** "Look at our milestones, the progress tracker, the to-do items on GitHub, and the changes
> waiting for review. What unfinished task matters most for getting our final dataset done? If it's in
> my area, or nobody has taken it, explain it to me."

### Step 5: Start a separate copy for this task (make a branch)
Claude names it with your workstream letter and a few words, like `a/bond-sample` or
`b/paragraphs`. Use **one branch per task**, kept small: roughly a day or two of work.
> **Say:** "Start a new branch for this task."

### Step 6: Plan the change, then make it
Point Claude at the relevant part of the design so it doesn't guess. **Use "plan" mode for this part.**
> **Say:** "Read section 11.2 of the design document. Then make a plan for handling dollar amounts
> that end with a period, in the step that reads budget items. Don't change anything yet."

You will probably need to revise the plan a few times before you tell Claude to start coding.

### Step 7: Check the work
> **Say:** "Run the automatic checks and explain any problems in plain language."

Also look at what changed (the **diff**: the list of exactly which lines changed; see §4). If you can't explain the change roughly in your
own words, ask Claude to walk you through it before you continue.

### Step 8: Share your work (commit, push and open a pull request)
> **Say:** "Save this work with a clear note about what changed, upload it, and propose it to the
> group. Show me which files you're including first."

Check that the list has **no** files from `data/raw/`, `data/interim/`, `data/output/`, `reports/`,
or anything with a key or password. The first time, Claude may ask you to log in to GitHub (see §7).

You don't need to wait for a review. At the start of the next work session, yours or a
classmate's, Step 2 reviews it and adds it to the group's shared version.

Then choose the next task at Step 4. In a new work session, start again at Step 1.

---

## 3. Words Claude will use

You don't need any of these words to ask Claude for something; plain language works. But Claude
may use them when it explains what it's doing. If it uses a word you don't know, look here, or ask
(§6).

| Word | Meaning | Analogy |
|---|---|---|
| **repo** (repository) | The project folder plus its full history | A shared drive folder that remembers every version |
| **`main`** | The official, shared version everyone builds on | The "final" copy of a group paper |
| **branch** | Your own working copy where you make changes without touching `main` | A "draft – Tierney" copy of the paper |
| **commit** | A saved snapshot of your changes, with a short message | Pressing save with a note about what changed |
| **push** | Upload your commits to GitHub | Syncing your draft to the cloud |
| **pull** | Download the latest commits from GitHub | Refreshing to get teammates' changes |
| **pull request (PR)** | A request to merge your branch into `main`, where teammates can comment | "Suggest changes" mode: anyone can accept it |
| **merge** | Fold a branch's changes into `main` | Accepting the suggested changes |
| **merge conflict** | Two people changed the same lines differently, so git asks a human which to keep | Two editors rewrote the same sentence |
| **CI** | Automatic checks GitHub runs on every PR (`ruff`, `pytest`, `validate`) | A spell-checker that blocks submission |
| **diff** | A view of exactly which lines changed | Track changes |

---

## 4. Doing it with the desktop app

Some things are easier to see in the app than through Claude's chat. This is what the app's
[documentation](https://code.claude.com/docs/en/desktop) describes. If your version looks
different, ask Claude ("where do I see my changes in this app?").

- **Opening the project.** Under **Local**, click the project-folder control and choose
  **Open folder…**, then pick `capstone-fall26`.
- **Seeing what changed (the diff, the list of changed lines).** Click the line counts (e.g. **+12 −1**) in the **Changes**
  card, or the **Changes** button in the title bar (shortcut ⌘⇧D). You can click **+** next to a
  line to leave Claude a comment on it, like "why did you remove this?".
- **How much Claude may do on its own.** The **permission mode** selector under the prompt box:
  - **Manual**: Claude asks before every edit and you accept or reject each one. Best while
    you're learning.
  - **Accept edits**: Claude edits files without asking but still asks before running commands.
  - **Plan**: Claude only investigates and proposes a plan; it doesn't change anything. Great for
    Step 6.
  - **Auto**: Claude proceeds on its own. Use it only for routine tasks you understand well.
- **Commands.** Type `/` in the prompt box to see the menu, including the project's `/start-task` and `/finish-task` (§2).
- **Getting a review of your changes.** Type `/code-review` in the prompt box before you share them.
- **Pull-request status.** After a PR is opened, the result of its CI (GitHub's automatic checks) shows in the **Changes** card.
- **Sharing your work.** The simplest reliable path is to ask Claude (Step 8), then check the
  **Changes** card. If you see a PR button in your version of the app, it's fine to use it.
- **Worktree toggle and parallel sessions (+ New).** Leave **Worktree** off unless you know you
  want it. It creates a separate copy of the repo on its own branch, which is confusing if you
  don't expect it. One session per task is plenty.

---

## 5. Taking a quick look at a teammate's PR (optional)

Reviews are optional: anyone can merge any PR whose automatic checks pass (Step 2). A quick look helps
when you want to understand a change, or something seems off. Let Claude do the checking:
> **Say:** "Review proposed change #12 against the checklist in section 5 of the workflow doc.
> Explain in plain language what it changes and anything that looks risky. Tell me what you'd fix
> before you change anything."

What Claude checks:
- ☐ CI is green (GitHub's automatic checks passed).
- ☐ The changes match what the description says.
- ☐ No generated files were edited by hand (`data/`, `reports/`, `review/review_queue.csv`).
- ☐ No new or renamed columns or allowed values unless `DESIGN.md` §7/§9 and `schemas.py` were updated too.
- ☐ The tracker in `OVERVIEW.md` or DESIGN §21 is updated if a milestone changed.

If it's fine, merge it. If something's wrong, have Claude fix it and then merge it, and leave a
short comment saying what you changed (Step 2).

---

## 6. Working well with Claude

### Two flavours of confusion
When you feel lost, first ask yourself *which kind* of confused you are.

**Flavour 1: "I've never heard of this."** Claude talks as if you'll obviously recognize a term,
tool, or step that is actually new to you, like "just rebase onto main" or "add a sample". **Slow down and ask for more context.**
> - "What is a rebase? Explain it as if I'm new to programming."
> - "Before we continue, why is this step needed?"
> - "Show me the file you're talking about and point to the line."

**Flavour 2: "This doesn't fit what I know."** Claude's approach clashes with what you know about
the actual laws, the data, or the project's goals. For example, it's building something elaborate
that our goal doesn't need, or you're being asked to decide between two options when both seem wrong. **Use your domain knowledge as the deciding factor.**
> - "That doesn't match what I know: the FY2025 GAA is missing most veto markup. How does your plan handle that?"
> - "Our goal is X. Why does this need Y?"
> - "This seems more complicated than the problem. What's the simplest version?"

### Other habits
- **Ask for a plan before edits** on anything non-trivial (you can use **Plan** mode for this).
- **Ask it to explain** code you don't understand. "What does this function do, line by line?"
  is a perfectly good question.
- **Keep PRs small.** One idea per PR is easier to review, test, and undo.
- **Look at the diff (the list of changed lines) before sharing.** Know what you're saving.
- **Watch for bloat.** If Claude adds a new file, setting, or helper you didn't ask for, ask
  whether it's needed. Less code means less to understand.
- **Start a fresh chat for a new task.** Long chats about many topics get muddled.

---

## 7. When things go wrong

Most of the time, you can just tell Claude what happened in your own words:
> **Say:** "Something went wrong: [what you saw]. Explain what happened in plain language, and tell
> me how you'd fix it before you change anything."

A few situations need you to act or decide:

| Situation | What to do |
|---|---|
| **You want to throw away changes** | "Show me what I'd lose first." Then, if you're sure: "Throw away my unsaved changes to these files." This can't be undone. |
| **Your changes clash with a teammate's** (a merge conflict) | "Two of us changed the same part of a file. Show me both versions of each part that clashes and explain them. Don't pick one until I decide." If you can't tell which is right, ask the teammate. |
| **Claude asks you to log in to GitHub** | Only you can do this. Open the Terminal app, run `gh auth login`, and follow the prompts (choose GitHub.com and "Login with a web browser"). Then go back to Claude. |
| **`No module named ma_approps`** | macOS has hidden the project's `.venv` folder. Run `chflags -R nohidden .venv`, or ask Claude to fix it. |

### First-time setup (once per computer)
> **Say:** "Set up this project on my computer, following the instructions in the README, and check
> that everything works."

That creates the `.venv` folder (the project's private copy of Python and its libraries), installs
the project, and runs `pytest` and `validate`. The contact email the `laws` stage sends to
malegislature.gov is already set in `config/settings.toml` (the group chose it; DESIGN §20, Q18).
