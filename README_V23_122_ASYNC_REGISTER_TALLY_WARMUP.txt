V23.122 — ASYNCHRONOUS REGISTER TALLY WARMUP

- Reads and deduplicates the PostgreSQL master register and Kobo membership
  register in a background worker when the voting service starts.
- Dashboard vote/result requests no longer wait for the large register load.
- A temporary failure in one register source no longer returns HTTP 500 for all
  six dashboard feeds.
- The last successful combined county tally remains available during temporary
  database or Kobo outages.
- Dashboard metadata reports whether register refresh is still running and any
  temporarily unavailable source.

Deploy this voting-system release before deploying or testing the dashboard
packages. On a cold start the first dashboard refresh may show zero briefly;
the dashboards' automatic refresh displays the combined tallies as soon as the
background warmup completes.
