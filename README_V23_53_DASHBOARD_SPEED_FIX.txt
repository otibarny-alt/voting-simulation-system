V23.53 — RESULTS FEED SPEED AND STATE REFRESH FIX

- Keeps the V23.52 opened/closed stream-state correction.
- Limits PostgreSQL connection waits to 5 seconds and statements to 12 seconds.
- Caches each of the six aggregate dashboard feeds for 15 seconds.
- Prevents repeated browser refreshes from rerunning the same large aggregation.

Deploy this package to the voting-simulation-system service before deploying
or refreshing any separate results dashboard.

