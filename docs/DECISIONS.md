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

## 2026-09-08 -- First successful live run against the real API

Ran `python -m ingestion.fetch_games --season 2024` against the live
balldontlie API (not just unit tests) for the first time. Confirmed:
auth via API key worked, pagination correctly followed cursors across
multiple pages, rate limiting kept requests under the 5/minute cap
without triggering a 429, and the output file landed in `storage/raw/`
with a non-zero record count. Also ran the full pytest suite -- all
passing. This is the first real evidence the ingestion logic works
end-to-end, not just against synthetic test data.