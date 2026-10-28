# Working with Claude Code and git

A refresher for the "how" of making progress on this project. For what the program does and who owns what, see [`OVERVIEW.md`](OVERVIEW.md).

---

## 1. The mental model

- **The program is the `.py` files** in `src/ma_approps/`. These are text files of
  Python code.
- **Chatting with Claude Code can change those files.** You can edit them yourself too, but if you are in "code" more (rather than the regular "chat" mode), Claude will directly program for you in your copy of these files.
- **Git saves and shares snapshots of the files.** Edits sit only on your computer until you
  **commit** them (save a snapshot), **push** them (upload to GitHub), and **merge** them (add them
  to the shared version). Teammates see your work only after it's merged, or if they look at your
  branch.

So the loop is: **ask Claude to edit files → check the edits → save a snapshot → share it for
review.**

---

## 2. Vocabulary

| Word | Meaning | Analogy |
|---|---|---|
| **repo** (repository) | The project folder plus its full history | A shared drive folder that remembers every version |
| **`main`** | The official, shared version everyone builds on | The "final" copy of a group paper |
| **branch** | Your own working copy where you make changes without touching `main` | A "draft – Tierney" copy of the paper |
| **commit** | A saved snapshot of your changes, with a short message | Pressing save with a note about what changed |
| **push** | Upload your commits to GitHub | Syncing your draft to the cloud |
| **pull** | Download the latest commits from GitHub | Refreshing to get teammates' changes |
| **pull request (PR)** | A request to merge your branch into `main`, where teammates can comment | "Suggest changes" mode, waiting for approval |
| **review** | A teammate reads your PR and approves it or asks for changes | Peer editing |
| **merge** | Fold an approved branch into `main` | Accepting the suggested changes |
| **merge conflict** | Two people changed the same lines differently, so git asks a human which to keep | Two editors rewrote the same sentence |
| **CI** | Automatic checks GitHub runs on every PR (`ruff`, `pytest`, `validate`) | A spell-checker that blocks submission |
| **diff** | A view of exactly which lines changed | Track changes |

---

## 3. The everyday loop

In each step, **"Say"** is something you can type to Claude. You don't need the exact
wording.

### Step 1: Start from the latest `main`
Make sure you're building on everyone's newest work.
> **Say:** "Switch to main and pull the latest changes. Tell me if I have any uncommitted work first."

### Step 2: Make a branch for this task
Name it with your workstream letter and a few words: `a/bond-sample`, `b/paragraphs`,
`c/figure-change`, `d/department-table`, `e/cthru-snapshot`. Use **one branch per task**, kept small:
roughly a day or two of work.
> **Say:** "Create a new branch called `b/paragraphs`."

### Step 3: Ask for the change
Point Claude at the relevant part of the design so it doesn't guess.
> **Say:** "Read DESIGN §11.2. Then make a plan for handling trailing periods on amounts in
> `read_items.py`. Don't edit anything yet."
>
> Then, once you understand and agree with the plan: "OK, go ahead."

### Step 4: Check the work
> **Say:** "Run `pytest` and `python -m ma_approps validate` and explain any failures in plain language."

Also look at the **diff** (see §4) so you know what actually changed. If you can't explain the
change roughly in your own words, ask Claude to walk you through it before you continue.

### Step 5: Commit
A good message says what changed and why, e.g. `read_items: allow trailing period after amount (2025 ch. 3)`.
> **Say:** "Commit these changes with a clear message. Show me which files you're including first."

Check that the list has **no** files from `data/raw/`, `data/interim/`, `data/output/`, `reports/`,
or anything with a key or password.

### Step 6: Push and open a pull request
> **Say:** "Push this branch and open a pull request. In the description, explain what changed, why,
> and how it was tested, and mention which DESIGN section it relates to."

Claude uses the `gh` tool for this. The first time, it may ask you to log in to GitHub (see §8).

### Step 7 (maybe optional): Get one teammate's review
Post the PR link in the group chat. Any one teammate can review (see §5). Wait for **CI to be
green** (a ✅ on the PR page) and **one approval**. You can also accept & merge your own PRs, but it's good practice to have a second set of eyes.

### Step 8: Merge and tidy up
Merge on the GitHub PR page with the green **Merge pull request** button, or:
> **Say:** "Merge PR #12, then switch back to main and pull."

Then start the next task at Step 1.

---

## 4. Doing it with the desktop app

Some things are easier to see in the app than through Claude's chat. This is what the app's
[documentation](https://code.claude.com/docs/en/desktop) describes. If your version looks
different, ask Claude ("where do I see my changes in this app?").

- **Opening the project.** Under **Local**, click the project-folder control and choose
  **Open folder…**, then pick `capstone-fall26`.
- **Seeing what changed (the diff).** Click the line counts (e.g. **+12 −1**) in the **Changes**
  card, or the **Changes** button in the title bar (shortcut ⌘⇧D). You can click **+** next to a
  line to leave Claude a comment on it, like "why did you remove this?".
- **How much Claude may do on its own.** The **permission mode** selector under the prompt box:
  - **Manual**: Claude asks before every edit and you accept or reject each one. Best while
    you're learning.
  - **Accept edits**: Claude edits files without asking but still asks before running commands.
  - **Plan**: Claude only investigates and proposes a plan; it doesn't change anything. Great for
    Step 3.
  - **Auto**: Claude proceeds on its own. Use it only for routine tasks you understand well.
- **Getting a review of your changes.** Type `/code-review` in the prompt box before you commit.
- **Pull-request status.** After a PR is opened, its CI status shows in the **Changes** card.
- **Committing and creating PRs.** The simplest reliable path is to ask Claude (Steps 5–6), then
  check the **Changes** card. If you see a PR button in your version of the app, it's fine to use
  it.
- **Worktree toggle and parallel sessions (+ New).** Leave **Worktree** off unless you know you
  want it. It creates a separate copy of the repo on its own branch, which is confusing if you
  don't expect it. One session per task is plenty.

---

## 5. Reviewing a teammate's PR

1. Open the PR link on GitHub, then the **Files changed** tab.
2. Not sure what you're looking at? Ask Claude:
   > **Say:** "Explain PR #12 to me in plain language: what it changes, why, and anything that looks risky."
3. Check:
   - ☐ CI is green.
   - ☐ The changes match what the description says, and stay mostly within the author's workstream.
   - ☐ No generated files were edited by hand (`data/`, `reports/`, `review/review_queue.csv`).
   - ☐ No new or renamed columns or allowed values unless `DESIGN.md` §7/§9 and `schemas.py` were updated too.
   - ☐ The tracker in `OVERVIEW.md` or DESIGN §21 is updated if a milestone changed.
4. Click **Review changes** and choose **Approve**, or **Request changes** with a comment. Kind,
   specific questions are a great review: "What happens if the amount has no `$`?"

Reviewing is real work, so spread it around. Try to review roughly as many PRs as you open.

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
- **Look at the diff before committing.** Know what you're saving.
- **Watch for bloat.** If Claude adds a new file, setting, or helper you didn't ask for, ask
  whether it's needed. Less code means less to understand.
- **Start a fresh chat for a new task.** Long chats about many topics get muddled.

---

## 8. When things go wrong

| Situation | What to say to Claude |
|---|---|
| **Tests fail** | "Run pytest and explain the failure in plain language. Is it caused by my change? Propose a fix but don't apply it yet." |
| **Merge conflict** | "I have a merge conflict. Show me both versions of each conflicting part and explain them. Don't resolve it until I choose." If it involves a teammate's work, ask them. |
| **Not sure what branch I'm on** | "Which branch am I on, and do I have uncommitted changes?" |
| **Want to throw away uncommitted changes** | "Show me what I'd lose first." Then, if you're sure: "Discard my uncommitted changes to these files." This can't be undone. |
| **Committed to `main` by accident** | "I committed to main by mistake and haven't pushed. Move that commit to a new branch called `x/...` and reset main to match GitHub." |
| **My branch is behind `main`** | "Bring the latest main into my branch and tell me if there are conflicts." |
| **`No module named ma_approps`** (but `pytest` works) | macOS has hidden the `.venv` folder. Run `chflags -R nohidden .venv`, or ask Claude to. |
| **Claude asks to log in to GitHub / `gh` not authenticated** Login is interactive, so open the Terminal app, run `gh auth login`, and follow the prompts (choose GitHub.com and "Login with a web browser"). Then go back to Claude. |
| **Totally lost** | "Summarize where I am: branch, uncommitted changes, last commit, and whether my PR exists." |

### First-time setup (once per computer)
> **Say:** "Set up this repo for me following the Quickstart in README.md, and run the tests."

That creates the `.venv` folder (the project's private copy of Python and its libraries), installs
the project, and runs `pytest` and `validate`. Also set `contact_email` in
`config/settings.toml` before anyone runs the `laws` stage (ask the group which address to use).
