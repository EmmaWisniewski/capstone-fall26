# The "laws" step, in plain language

*For readers with no programming background. Owner: workstream A (Emma). The technical
description is in [DESIGN §6](../DESIGN.md#6-pipeline-architecture) and
[§7.15](../DESIGN.md#715-datarawmanifestcsv-written-by-laws); the program itself is
`src/ma_approps/laws.py`. Last updated 2026-10-28.*

**The short version:** this part of the program goes to the Massachusetts Legislature's website,
collects the full text of the spending laws on our list, and saves a copy of each one on our
computer. Everything else in the project reads those saved copies.

## Why we need it

Our dataset is built from the wording of the laws themselves: the line items, the dollar amounts,
the changes to earlier budgets. Before anyone can read those laws, someone has to collect them.
This step is that collecting.

## What it does, step by step

1. **It reads our list of laws.** The group keeps a spreadsheet of every law we've decided to
   include (`config/law_list.csv`). The program reads that list to know which laws to collect.
   Laws marked "excluded" are skipped.
2. **It asks the Legislature's website for each year's laws.** The website hands out all of a
   year's laws in one go. So instead of asking once per law, the program asks once per year.
3. **It picks out the laws we want.** From each year's batch, it pulls out only the laws on our
   list and saves each one as its own file.
4. **It keeps a receipt.** For every file saved, it writes down where the file came from, when it
   was saved, its size, and a "fingerprint" that lets us check later whether the file has
   changed. This receipt is `manifest.csv`.

## How it behaves politely

The Legislature's website is a public service, so the program is careful with it:

- **It doesn't rush.** It waits about one second between requests, so it never floods the site.
- **It says who it is.** Every request includes our project's name and a contact email, so the
  site's staff can reach us if there's a problem. Until the group adds an email, the program
  refuses to contact the site at all.
- **It never asks twice for the same thing.** If a law has already been saved, the program uses
  the saved copy instead of downloading it again.
- **It's patient when the site is busy.** If the site says "try again later", the program waits a
  bit longer each time before trying again, and gives up after a few tries.
- **One problem doesn't stop everything.** If one law can't be collected, the program notes it and
  carries on with the rest.

## What it doesn't do yet

It only collects laws that people have already put on our list. It doesn't yet search the website
on its own for new spending laws we might have missed. That's planned next, so that future
researchers can find each new year's laws automatically.

## How we know it works

- **Practice runs.** Automatic checks pretend to be the website, so we can test the program's
  behavior without contacting the real site. They run every time anyone proposes a change.
- **A real run.** On October 28, 2026, we ran it against the real website. It collected all 52
  laws on our list in 8 requests, with no errors, in about 18 seconds.
- **Matching our reference copies.** The project keeps saved copies of 6 laws for testing. The
  fresh downloads matched them exactly, character for character.
- **Matching our list.** For all 52 laws, the dates, official titles and bill numbers on our
  spreadsheet matched what the website says.

## Where the files go

The saved laws are kept in a folder on each team member's own computer (`data/raw/`). They aren't
uploaded to the shared project, because anyone can collect them again by running this step.
