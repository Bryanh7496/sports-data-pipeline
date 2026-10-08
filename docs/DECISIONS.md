# Engineering Decisions Log

Short, dated notes on non-obvious choices and why they were made. The goal
isn't a full ADR template -- it's to capture the reasoning while it's fresh,
so it can be reused later (in a README, in an interview, or just by future-me
wondering why something was built a certain way).

## 2026-08-27 -- Client-side rate throttling instead of reactive backoff only

The free balldontlie tier allows 5 requests/minute. Chose to sleep a fixed
interval (60s / rate limit) between every request rather than firing as fast
as possible and only backing off after hitting a 429. Firing-then-backing-off
still works, but it wastes the first request of every burst on discovering
the limit, and repeated 429s are more likely to trigger a temporary IP-level
block on a free tier. Paying the fixed delay up front is slower per-run but
more predictable and less likely to get throttled harder.

## 2026-08-27 -- Local filesystem as a stand-in for S3

Landing raw JSON to `storage/raw/` locally instead of S3 for now. AWS setup
is a separate, later phase of the plan (Month 2) and there's no reason
ingestion logic (auth, pagination, retries, validation) needs to wait on it.
`write_raw_json()` is the single function that will change when S3 gets
added -- everything upstream of it stays the same. This is also why it's a
separate function rather than inlined into the main loop.

## 2026-08-27 -- Fail fast on 4xx (except 429), retry on 429/5xx/network errors

A 401 (bad API key) or a malformed request isn't going to fix itself on
retry -- retrying it three times with backoff just delays a should-be-instant
failure. Only genuinely transient conditions (rate limit hit, server error,
network blip) get the retry-with-backoff treatment.

## 2026-09-09 -- Least-privilege IAM user instead of root credentials

Created a dedicated IAM user (`sports-pipeline-app`) scoped to a single
custom policy granting only `s3:ListBucket` on the bucket itself and
`s3:PutObject`/`s3:GetObject` on objects within it -- no `DeleteObject`, no
wildcard resources, no broad managed policy like `AmazonS3FullAccess`. The
pipeline's code should never hold credentials more powerful than what it
actually needs; if these access keys ever leaked, the blast radius is
"read/write one bucket," not "full AWS account access."

## 2026-09-09 -- Write locally first, then upload to S3 (not a direct S3 write)

`fetch_games.py` still writes the raw JSON to local disk first via
`write_raw_json()`, then calls `upload_file()` (new, in
`ingestion/s3_uploader.py`) to push that same file to S3. Considered
writing directly to S3 and skipping the local file entirely, but kept the
local-write step because: (1) it preserves a debuggable local artifact
during development without needing to go pull it back down from S3 to
inspect it, and (2) the existing unit tests for `write_raw_json()` didn't
need to change. The tradeoff: if the S3 upload fails after a successful
local write, the file exists locally but not in S3 -- there's no automatic
retry/reconciliation for that gap yet, just a loud log error. That's an
acceptable gap for a single-user/manual-run pipeline at this stage, but is
exactly the kind of thing that would need addressing (e.g. a
"reconcile local vs. S3" check, or an idempotent re-run) before this ran
unattended under Airflow.

## 2026-09-09 -- S3 upload errors are separated from ingestion errors

`S3UploadError` is a distinct exception type from `BallDontLieAPIError`.
A failed upload after a successful, fully-validated data pull is a
different kind of failure than a failed API call -- the data itself is
fine, it just isn't in the right place yet. Keeping these as separate
exception types means calling code (and future monitoring/alerting) can
distinguish "the data is bad or unavailable" from "the data is fine but
storage failed," which likely warrant different responses.

## 2026-09-09 -- S3 Upload completed and in raw storage folder

I hit real rate limits and watched my retry logic handle them correctly

## 2026-10-08 -- Land raw JSON as a single VARIANT row; flatten and dedupe in dbt

Loaded each S3 file into `SPORTS_DB.RAW.GAMES_RAW` as one VARIANT row
(payload, source_file, file_row_number, loaded_at) instead of flattening
during COPY INTO. Snowflake's COPY transformation step doesn't support
FLATTEN, and keeping RAW as an untouched copy of what the API returned
means parsing mistakes can be fixed in dbt and replayed without
re-calling the API (a full season takes about 3 minutes at the 5
requests/minute limit). Trade-off: one file = one row, so this relies on
the 16 MB VARIANT limit. A full season is ~1.7 MB, so it's fine here but
wouldn't scale to much larger payloads.

## 2026-10-08 -- Idempotent loads are not the same as unique data

COPY INTO tracks which files it has already loaded, so re-running it
doesn't double-load a file. But every ingestion run lands a full season in
a new timestamped file, so the same game_id appears once per file. The
staging model `stg_games` therefore deduplicates on game_id, keeping the
row from the latest extracted_at (QUALIFY ROW_NUMBER). The `unique` test
on game_id enforces this. Grain of stg_games: one row per game.

## 2026-10-08 -- Snowflake reads S3 through an IAM role, not access keys

Created a storage integration (`s3_sports_integration`) backed by an IAM
role (`snowflake-s3-read-role`) that Snowflake's own AWS identity assumes,
with an external ID in the trust policy. The role's policy is read-only
and limited to the `raw/` prefix (GetObject, plus ListBucket restricted
by prefix condition). No AWS keys are stored in Snowflake. This is the
role-vs-user distinction in practice: the pipeline's code uses an IAM
user with keys (it runs on my laptop); a managed service uses a role.

## 2026-10-08 -- Resource monitor and a small warehouse as a cost guardrail

After converting the trial to paid, set the warehouse to X-Small with
60-second auto-suspend and attached a resource monitor
(`sports_pipeline_monitor`, 5 credits/month): notify at 50% and 90%,
suspend at 100%, suspend immediately at 110%. The workload is a few
thousand rows, so the cap should never bind in normal use; it exists so a
mistake (a runaway query or loop) is contained. Same blast-radius thinking
as the scoped IAM policy and the AWS billing alarm.

## 2026-10-08 -- Dedicated least-privilege role for dbt (DBT_ROLE)

dbt runs as `DBT_ROLE`, not ACCOUNTADMIN. It can use the warehouse, read
the RAW schema (existing and future tables), and create its own schemas
(STAGING, MARTS). It owns what it creates. Side effect worth remembering:
objects owned by DBT_ROLE are invisible to ACCOUNTADMIN unless the role
is granted up the hierarchy, which surfaced as a "schema does not exist or
not authorized" error when I queried as ACCOUNTADMIN. A macro
(`generate_schema_name`) makes dbt use the custom schema name as-is
(STAGING, not ANALYTICS_STAGING).

## 2026-10-08 -- Key-pair auth with a service user, not password + MFA

Snowflake required MFA for password sign-ins on this account, which a
non-interactive tool like dbt can't satisfy. Switched to key-pair
authentication with a dedicated service user (`DBT_SERVICE_USER`,
TYPE = SERVICE, which can't use a password). The private key lives in
`~/.snowflake/` outside the repo, is referenced only through an
environment variable, and `*.p8` is gitignored as a backstop. profiles.yml
contains no secrets, so it's safe to commit. Considered MFA token caching
with the human user; rejected as more fragile and a worse fit for
automation (Airflow later).

## 2026-10-08 -- Pinned the local runtime to Python 3.12

dbt crashed on startup with a mashumaro serialization error under the
default Python. Rebuilt the venv on Python 3.12 (installed from
python.org after a Homebrew update left Homebrew itself broken) and dbt
ran cleanly. I suspect a Python-version incompatibility but didn't
confirm which version I started on, so treat that as likely, not proven.
Also had to run the Python installer's "Install Certificates" script
before pip could build one dbt dependency. Lesson: record the runtime
version, because "works on my machine" depends on it.