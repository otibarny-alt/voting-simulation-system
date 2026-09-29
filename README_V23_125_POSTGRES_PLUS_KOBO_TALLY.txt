V23.125 — POSTGRESQL + LIVE KOBO REGISTER TALLY

Registered voters are calculated as:

  unique active PostgreSQL National IDs
  + unique live Kobo Membership National IDs absent from PostgreSQL

- PostgreSQL geographic totals are published first, so the dashboards do not
  display zero while the Kobo dataset is still being downloaded.
- Kobo submissions are then deduplicated by National ID and Kobo-only voters
  are added to the appropriate county, constituency and ward.
- PostgreSQL schema and aggregate query timeouts are increased from 4 seconds
  to 120 seconds for background tally work on Render.
- Any dashboard payload created before either stage is invalidated immediately.
- A complete PostgreSQL + Kobo union remains stored as the durable last-good
  tally shared by all application workers.

Deploy this voting-system package only. Existing V3 dashboard packages remain
compatible and do not need redeployment.
