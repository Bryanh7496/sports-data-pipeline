# Project context for Claude Code

## Who's working on this and why

I'm a data analyst (5+ years) with strong Snowflake and dbt experience,
working toward a Data Engineer role. This project is a hands-on learning
portfolio piece, not just a repo I want finished — the point is for *me* to
understand every part of it, not to have it built for me.

**Because of that: explain what you're doing and why before making
non-trivial changes.** A one-line "why" is enough for small stuff (e.g. "adding
a .gitignore entry for the venv folder") but for anything architectural,
walk me through the reasoning like you would if teaching the concept, not
just applying it.

I'm relatively new to a lot of this stack (Python-as-an-engineering-language,
AWS, Airflow, production data pipeline patterns) even though I'm strong in
SQL/Snowflake/dbt. Assume I need concepts explained, not just code.

## Working style preferences

- **Let me run git commands myself** where reasonable (add/commit/push).
  I'm building the habit of the git workflow, not just trying to get commits
  made. It's fine for you to tell me exactly what to run and why.
- Prefer smaller, explained steps over large autonomous multi-file changes,
  especially for new concepts I haven't worked with yet (S3, Airflow, etc.).
- When something breaks, treat it as a teaching moment — explain what the
  error means and why the fix works, not just the fix itself.
- I'm on macOS, using zsh, with Python installed via Homebrew (which means
  `pip`/`python` don't work directly — use `python3`, and note that a venv
  is required due to PEP 668 "externally managed environment" restrictions).

## Project overview

A production-style data pipeline built as a learning project, following a
Data Analyst -> Analytics Engineer -> Data Engineer roadmap. Full
architecture, design decisions, and roadmap are documented in:

- `README.md` — architecture, current status, how to run it, roadmap checklist
- `docs/DECISIONS.md` — dated log of engineering trade-offs and reasoning

**Read both of those at the start of a session** — they're kept up to date
and are the source of truth for what's built, what's tested, and what's next.

## Current phase (update this section as the project progresses)

Phase 1 (Python ingestion) is complete and verified: pulls NBA game data
from the balldontlie API with auth, rate limiting, retries, pagination, and
record validation; lands raw JSON locally; has a passing pytest suite; CI
runs on every push via GitHub Actions.

Next up: Phase 2 — land raw data to S3 instead of local disk, then load into
Snowflake RAW schema. This is also my first real hands-on AWS work, so
expect to need more explanation here than in areas I already know.

## Longer-term roadmap

See the checklist in `README.md` for the full list, but roughly: S3 landing
-> Snowflake load -> dbt staging/marts + tests -> Airflow orchestration ->
deliberately breaking the system and documenting recovery -> monitoring.

## A note on git history

I use SSH auth for this repo (not HTTPS/tokens) after working through some
GitHub auth issues early on. If you ever need to check remote config,
`git remote -v` should show a `git@github.com:...` URL.
