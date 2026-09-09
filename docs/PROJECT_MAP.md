# Project Map: Order of Operations & File Reference

This document explains what runs when, what each file is for, and which
tool (if any) it depends on. Read this alongside `README.md` (the
architecture/status overview) and `docs/DECISIONS.md` (the reasoning behind
specific choices) -- this file is the "what and where," those are the
"why and current state."

Update this file whenever a new phase adds real files (Snowflake loading,
dbt models, an Airflow DAG) -- the "Planned" sections below are placeholders
for exactly that.

---

## Order of operations (current: Phase 2, ingestion + S3 landing)

This is the actual runtime sequence when you run:
```bash
python -m ingestion.fetch_games --season 2024
```

```
1. ingestion/config.py
   |  load_dotenv() reads .env, Settings.from_env() validates every
   |  required value is present (API key, AWS credentials, bucket name)
   |  and fails immediately with a specific error if anything's missing.
   v
2. ingestion/client.py
   |  BallDontLieClient authenticates to the balldontlie API and pulls
   |  games page by page, throttling itself to stay under the rate
   |  limit and retrying on 429/5xx errors with exponential backoff.
   |  Yields one game record at a time (it's a generator).
   v
3. ingestion/fetch_games.py  (validate_game + write_raw_json)
   |  As each game streams in from step 2, validate_game() checks it has
   |  every field the pipeline depends on downstream, dropping anything
   |  incomplete. Once all pages are consumed, write_raw_json() saves the
   |  validated batch to storage/raw/ as a timestamped JSON file.
   |  NOTE: steps 2 and 3's validation are interleaved in real time --
   |  the diagram shows clean blocks, but records are validated as they
   |  arrive, not after every page is already fetched.
   v
4. ingestion/s3_uploader.py
   |  upload_file() takes the local JSON file from step 3 and uploads
   |  it to S3 via boto3, authenticating as the least-privilege
   |  sports-pipeline-app IAM user. Returns the s3:// URI on success.
   v
5. S3 bucket (sports-data-pipeline-bryanh-314, raw/ prefix)
      The landed, durable copy of this run's data. This is what the
      next phase (Snowflake loading) will read from.
```

**Not shown as its own step, because it isn't sequential:**
`ingestion/utils/logger.py` provides the shared logging setup every other
module calls into -- it's a utility every step uses, not a stage in the
flow itself.

---

## File reference

### `ingestion/config.py`
- **What it does:** Defines the `Settings` dataclass and `Settings.from_env()`,
  which reads every required environment variable, validates presence,
  and raises a clear `ConfigError` if anything's missing.
- **Why it's needed:** Centralizes all configuration in one place so the
  same code runs unchanged across local dev, CI, and (later) Airflow --
  only the environment variables differ between environments, never the
  code.
- **Tool-specific?** No -- pure Python (`os`, `dataclasses`, `pathlib`).
  Reads values that happen to be AWS/API-related, but the file itself
  has no AWS or API dependency.

### `ingestion/client.py`
- **What it does:** `BallDontLieClient` wraps all communication with the
  balldontlie API: authentication, client-side rate limiting, retry
  with exponential backoff, and cursor-based pagination via
  `get_games()`.
- **Why it's needed:** Isolates every API-specific concern (HTTP status
  codes, pagination cursors, rate limits) in one place so the rest of
  the pipeline never has to know or care how the API works.
- **Tool-specific?** balldontlie API-specific (via the `requests`
  library). Not tied to AWS, Snowflake, or dbt.

### `ingestion/fetch_games.py`
- **What it does:** The entry point. Defines `validate_game()` (schema
  check on each record), `write_raw_json()` (saves a batch locally),
  and `run()` (orchestrates: pull from the client, validate, write
  locally, then call the S3 uploader). This is the file you actually
  invoke with `python -m ingestion.fetch_games`.
- **Why it's needed:** Something has to coordinate the other modules in
  the right order and handle the top-level success/failure logic
  (e.g. an empty result set isn't an error, but a failed API call is).
- **Tool-specific?** No -- pure Python orchestration logic. Imports
  from `client.py`, `config.py`, and `s3_uploader.py`, but doesn't
  contain AWS or API specifics itself.

### `ingestion/s3_uploader.py`
- **What it does:** One function, `upload_file()`, which uploads a local
  file to S3 using `boto3`, builds the S3 key from the configured
  prefix, and wraps failures in a distinct `S3UploadError`.
- **Why it's needed:** Keeps "land data locally" (fetch_games.py) and
  "get it into S3" as separate, independently testable concerns --
  this is also the one file that would change if the destination ever
  moved away from S3.
- **Tool-specific?** **AWS-specific** (via `boto3`). This is the only
  file in the project with a direct AWS dependency.

### `ingestion/utils/logger.py`
- **What it does:** `get_logger()` returns a consistently-configured
  Python `logging.Logger` so every module's output has the same
  timestamp/level/module/message format.
- **Why it's needed:** Consistent, greppable logs across every module,
  set up in exactly one place instead of each file configuring logging
  differently.
- **Tool-specific?** No -- Python's built-in `logging` module only.

### `tests/test_fetch_games.py`
- **What it does:** Unit tests for `validate_game()` and
  `write_raw_json()` -- the parts of the pipeline that don't require
  hitting the live API, using synthetic game records and `pytest`'s
  `tmp_path` fixture for filesystem isolation.
- **Why it's needed:** Verifies core logic works correctly without
  depending on the external API being available or rate limits being
  a concern -- this is what runs in CI on every push.
- **Tool-specific?** `pytest`-specific, otherwise plain Python.

### `.github/workflows/ci.yml`
- **What it does:** A GitHub Actions workflow that checks out the repo,
  installs dependencies, and runs the pytest suite on every push and
  pull request to `main`.
- **Why it's needed:** Automated verification that changes haven't
  broken anything, without you needing to remember to run tests
  manually before every push.
- **Tool-specific?** **GitHub Actions-specific** (the YAML syntax and
  triggers are GitHub's). Runs plain `pytest` underneath.

### `.env` / `.env.example`
- **What it does:** `.env.example` is the checked-in template listing
  every environment variable the pipeline needs, with blanks for
  secrets. `.env` (gitignored, never committed) is your real local copy
  with actual values filled in.
- **Why it's needed:** Keeps secrets (API keys, AWS credentials) out of
  git history entirely while documenting exactly what configuration
  the project expects.
- **Tool-specific?** No -- `.env` is a convention, read by
  `python-dotenv` in `fetch_games.py`.

### `requirements.txt`
- **What it does:** Pins the Python packages this project depends on
  (`requests`, `pytest`, `python-dotenv`, `boto3`).
- **Why it's needed:** Reproducible installs -- anyone (including a
  future you, or CI) can run `pip install -r requirements.txt` and get
  the exact same dependencies.
- **Tool-specific?** No -- standard `pip` convention.

### `README.md`
- **What it does:** The project's front door -- architecture, current
  phase status, design-decision callouts, how to run it locally, and
  the roadmap checklist.
- **Why it's needed:** Written as a case study for anyone (a hiring
  manager, future-you) trying to understand the project without
  reading every line of code first.
- **Tool-specific?** No.

### `docs/DECISIONS.md`
- **What it does:** A dated, append-only log of engineering trade-offs
  and the reasoning behind them (e.g. why client-side rate throttling,
  why local-write-then-upload instead of direct S3 write, why a
  scoped IAM policy instead of a managed one).
- **Why it's needed:** Captures reasoning while it's fresh, for reuse in
  interviews, in the README, or just for future-you wondering why
  something was built a certain way.
- **Tool-specific?** No.

### `docs/GIT_WORKFLOW.md`
- **What it does:** A quick-reference cheat sheet of the git commands
  used day-to-day on this project (add/commit/push/pull, checking
  status and diffs).
- **Why it's needed:** So the core workflow is handy without needing to
  ask or search for it every session.
- **Tool-specific?** **Git-specific.**

### `CLAUDE.md`
- **What it does:** Persistent context read automatically by Claude Code
  at the start of every session in this project: who's working on it,
  the learning-focused working style, current phase, and environment
  notes (macOS/zsh/Homebrew venv requirements).
- **Why it's needed:** So any new Claude Code session picks up exactly
  where the last one left off, without you re-explaining context every
  time.
- **Tool-specific?** **Claude Code-specific** (this exact filename and
  location is a Claude Code convention).

---

## Planned files (not yet built)

These are placeholders for upcoming phases -- listed here so the "what
goes where" question is answered in advance, even though the files don't
exist yet.

### `dbt/` (Phase 3 -- not yet built)
- **What it will do:** Staging, intermediate, and marts models
  transforming the raw Snowflake data into clean, tested analytics
  tables, plus dbt tests (`not_null`, `unique`, `relationships`, etc.).
- **Tool-specific?** **dbt-specific**, running against Snowflake.

### `airflow/dags/` (Phase 4 -- not yet built)
- **What it will do:** A DAG definition orchestrating the full pipeline
  end-to-end: trigger ingestion, wait for S3 landing, trigger the
  Snowflake load, then trigger dbt runs and tests -- on a schedule,
  with retries and failure alerting instead of manual runs.
- **Tool-specific?** **Airflow-specific.**
- **Docker note:** This phase is also where Docker becomes relevant to
  this project. Airflow is a small ecosystem (scheduler, web server,
  metadata database, workers), and the standard way to run it locally
  is via `docker-compose`, which starts all of those pieces as
  coordinated containers with one command. A venv (what the project
  uses today) isolates Python packages; Docker isolates the entire
  environment (Python version, OS-level libraries, everything) --
  overkill for the single-script ingestion phase, but the practical
  answer once Airflow's multiple moving parts enter the picture. Not
  needed before this phase.

### Snowflake RAW schema loading (Phase 3 -- not yet built)
- **What it will do:** A script or Snowflake feature (e.g. `COPY INTO`,
  Snowpipe) that loads the JSON files landed in S3 into a raw Snowflake
  table, ready for dbt to transform.
- **Tool-specific?** **Snowflake-specific** (and reads from the
  AWS-specific S3 bucket this phase already built).

---

## Quick answer: "is this file tool-specific?"

| File | Tool dependency |
|---|---|
| `config.py` | None (pure Python) |
| `client.py` | balldontlie API (via `requests`) |
| `fetch_games.py` | None (orchestration only) |
| `s3_uploader.py` | **AWS** (`boto3`) |
| `utils/logger.py` | None (Python stdlib) |
| `test_fetch_games.py` | `pytest` |
| `.github/workflows/ci.yml` | **GitHub Actions** |
| `.env` / `.env.example` | None (convention + `python-dotenv`) |
| `requirements.txt` | None (`pip` convention) |
| `README.md`, `docs/*.md` | None |
| `CLAUDE.md` | **Claude Code** |
| `dbt/` *(planned)* | **dbt** + Snowflake |
| `airflow/dags/` *(planned)* | **Airflow** (run locally via **Docker**/`docker-compose`) |
