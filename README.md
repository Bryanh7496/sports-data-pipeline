# Sports Data Pipeline (NBA)

A production-style data pipeline built as a personal project to bridge a
Data Analyst → Analytics Engineer → Data Engineer transition. It ingests
NBA game data from a public API, lands it, transforms it, and (in later
phases) orchestrates and monitors the whole thing.

This README is written as a case study, not just a file listing -- the
design decisions and failure handling are the point of the project, not
just the final dashboard.

## Current status

**Phase 1 of 4 -- Python ingestion.** This phase pulls NBA games from the
[balldontlie API](https://docs.balldontlie.io/), validates them, and lands
raw JSON to local storage. It does **not** yet include Snowflake loading,
dbt transforms, or Airflow orchestration -- those are tracked below and
will be added as the project progresses.

```
[ DONE ]   API  ->  Python (auth, pagination, retries, validation)  ->  raw JSON (local)
[ NEXT ]   raw JSON  ->  S3  ->  Snowflake RAW
[ LATER ]  Snowflake RAW  ->  dbt staging/marts  ->  dbt tests
[ LATER ]  Airflow DAG orchestrates the full pipeline end-to-end
```

## Why this project

Coming from a Data Analyst / Analytics Engineer background (Snowflake, dbt,
SQL, stored procedures), the skill gap toward Data Engineering isn't
warehouse modeling -- it's everything upstream of the warehouse: reliably
getting data *into* the system in the first place, and building it so it
keeps working when the API changes shape, rate-limits you, or goes down
for an afternoon.

## Architecture decisions worth calling out

- **Client-side rate limiting, not just reactive backoff.** The free API
  tier allows 5 requests/minute. The client throttles itself to that rate
  proactively instead of firing as fast as possible and backing off after
  a 429 -- more predictable, less likely to get temporarily blocked.
- **Fail fast vs. retry, chosen per error type.** A bad API key (401) fails
  immediately -- retrying it three times just delays an error that isn't
  going to resolve itself. A rate limit hit (429) or server error (5xx)
  retries with exponential backoff, since those usually *are* transient.
- **Validation before landing, not just in dbt.** Records missing fields
  the pipeline depends on downstream (`id`, `date`, teams, `season`) are
  dropped and logged at ingestion time, not silently passed through to be
  caught later. This is a narrower check than what dbt tests will do once
  the data reaches the warehouse -- the goal here is "is this record even
  usable," not full schema validation.
- **Local storage today, S3 next.** Raw JSON lands to `storage/raw/` for
  now rather than S3, since there's no reason ingestion logic needs to wait
  on AWS setup. `write_raw_json()` in `ingestion/fetch_games.py` is the one
  function that changes when S3 is added.

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for the full, dated log of
these and future decisions.

## What happens when things break

Part of this project is deliberately testing failure modes rather than
just the happy path. As each one gets tested, it's documented here with
what happened and how the pipeline responded.

| Scenario | Status | Notes |
|---|---|---|
| Invalid/missing API key | Handled | Fails immediately with a clear error, no wasted retries |
| Rate limit (429) hit | Handled | Exponential backoff, up to `MAX_RETRIES` |
| Server error (5xx) | Handled | Exponential backoff, up to `MAX_RETRIES` |
| Malformed/incomplete record in response | Handled | Record dropped and logged, pipeline continues |
| Empty result set for a season | Handled | Logged as a warning, no file written, exits cleanly (not an error) |
| Network timeout mid-pagination | Planned | Not yet tested |
| Duplicate records across runs | Planned | Will matter once Snowflake loading (MERGE/upsert) is added |
| Airflow task failure / retry | Planned | Phase 4 |

## Project layout

```
sports-data-pipeline/
├── ingestion/
│   ├── client.py        # API client: auth, rate limiting, retries, pagination
│   ├── config.py        # Settings loaded from environment variables
│   ├── fetch_games.py   # Entry point: fetch -> validate -> land raw JSON
│   └── utils/
│       └── logger.py
├── storage/
│   └── raw/              # Landed raw JSON (gitignored; stand-in for S3 today)
├── dbt/                  # Placeholder -- transforms land here in the next phase
├── airflow/
│   └── dags/              # Placeholder -- orchestration lands here later
├── tests/
│   └── test_fetch_games.py
├── docs/
│   └── DECISIONS.md      # Dated log of engineering trade-offs
├── .github/workflows/ci.yml   # Runs the test suite on every push/PR
├── .env.example
└── requirements.txt
```

## Running it locally

1. Get a free API key at [app.balldontlie.io](https://app.balldontlie.io)
   (Account Settings → API).
2. Copy `.env.example` to `.env` and add your key.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the ingestion script for a given season:
   ```bash
   python -m ingestion.fetch_games --season 2024
   ```
   Output lands in `storage/raw/games_season2024_<timestamp>.json`.
5. Run the tests:
   ```bash
   pytest tests/ -v
   ```

## Roadmap

- [x] Python ingestion: auth, pagination, rate limiting, retries, validation
- [x] Unit tests + CI (GitHub Actions)
- [ ] Land raw data to S3 instead of local disk
- [ ] Load raw data into Snowflake (RAW schema)
- [ ] dbt staging/intermediate/marts models + tests
- [ ] Airflow DAG orchestrating ingestion → load → transform → test
- [ ] Deliberately break the system (malformed data, duplicate runs, task
      failures) and document recovery in the table above
- [ ] Monitoring/alerting on pipeline failure

## Background

This project follows a self-directed Data Analyst → Analytics Engineer →
Data Engineer learning plan built around existing Snowflake/dbt experience.
Full reasoning behind the phased approach is in `docs/DECISIONS.md`.
