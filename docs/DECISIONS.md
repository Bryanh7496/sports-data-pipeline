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