V23.160 — LIVE VOTERS-REGISTER DASHBOARD TOTALS

- Fixes dashboard totals lagging behind the voters register after membership
  additions or geographic edits.
- Immediately updates the durable county/constituency/ward tally after an
  approved PostgreSQL master-register change.
- Every dashboard snapshot reloads the small durable tally so all Render
  Gunicorn workers see changes made by another worker.
- Retains background PostgreSQL + Kobo reconciliation as a safety check.
- Use with the six ODM dashboard packages that read registered_voter_breakdown
  and calculate polling-station streams from county_main.csv.
- No manual database migration is required.
