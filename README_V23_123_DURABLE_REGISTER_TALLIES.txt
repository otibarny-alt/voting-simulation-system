V23.123 — DURABLE REGISTERED-VOTER TALLIES

- Fixes the zero registered-voter result caused by a failed cold-start refresh
  being cached as a successful empty result for five minutes.
- Failed or incomplete source reads are retried instead of being treated as a
  valid zero tally.
- Stores the last complete database-register + Kobo-register geographic tally
  in shared PostgreSQL so every Render worker and every dashboard uses the same
  result after restarts.
- Publishes a new durable tally only when both configured register sources have
  completed successfully; a temporary source outage keeps the last good count.
- Register loading remains outside the dashboard request path, preserving the
  fast Expected Streams and results response introduced in V23.122.

Deploy this voting-system release. The existing six V3 dashboard packages do
not need to be redeployed. After the first complete background refresh, the
registered-voter figure is retained across later service restarts.
