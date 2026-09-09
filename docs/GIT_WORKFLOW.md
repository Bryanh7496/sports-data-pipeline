# Git Workflow Cheat Sheet

Quick reference for the day-to-day git commands used on this project.
This isn't a full git tutorial -- just the handful of commands that cover
99% of what comes up while working solo on this repo.

## The standard cycle (every time you make changes)

Run these in order, from the project root, with your venv activated:

```bash
git status
```
Shows what's changed. Good habit to check this first so you know what
you're about to commit -- especially useful for catching a file you
didn't mean to touch.

```bash
git add .
```
Stages all changed files for commit. To stage only specific files instead
of everything:
```bash
git add ingestion/fetch_games.py docs/DECISIONS.md
```

```bash
git commit -m "Short description of what changed and why"
```
Commits the staged changes. Keep messages specific and in the present
tense -- "Add S3 upload logic" is more useful to future-you scrolling
through history than "updates" or "fix stuff".

```bash
git push
```
Sends your committed changes up to GitHub. The very first push on a new
branch needs `git push -u origin main` (sets up the link between your
local branch and GitHub's), but after that, plain `git push` works.

## Pulling changes down

```bash
git pull
```
Brings down anything that's on GitHub but not in your local folder --
e.g. if you ever edit a file directly on GitHub's website, or work from
a different machine. Run `git status` first to make sure you don't have
uncommitted local changes that could conflict.

## Checking things without changing anything

```bash
git log --oneline
```
Shows commit history, one line per commit. Good for seeing project
progress at a glance, or finding a specific past change.

```bash
git diff
```
Shows the exact line-by-line changes you've made but haven't committed
yet. Useful right before `git add` to sanity-check scope.

```bash
git remote -v
```
Confirms which GitHub repo this folder is connected to, and whether it's
using SSH (`git@github.com:...`) or HTTPS.

## The mental model

- `git pull` = bring GitHub's changes down to your machine
- `git add` + `git commit` + `git push` = send your machine's changes up to GitHub
- Neither direction happens automatically -- both require you to run the command.
- The two copies (local and GitHub) only match right after a pull or a
  push. They can silently drift apart if you edit one side without
  syncing (this happened once already in this project -- see the
  2026-09 entries in this file's git history if you ever want the
  full story of how that got resolved).

## This project's auth setup

This repo uses SSH authentication (not HTTPS/tokens) to talk to GitHub.
If you ever see an authentication error, check `git remote -v` first --
it should show a `git@github.com:...` URL, not `https://github.com/...`.
