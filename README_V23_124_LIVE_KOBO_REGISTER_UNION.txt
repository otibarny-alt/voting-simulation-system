V23.124 — LIVE KOBO + DATABASE REGISTER UNION

- Registered-voter dashboard tallies now read the current Kobo Membership
  Registration submissions, not the potentially stale membership CSV stored
  in Kobo form media.
- Keeps only the latest Kobo submission for each normalized National ID.
- Counts every active database-register National ID once, then adds only Kobo
  National IDs that are absent from the database register.
- Uses the current Kobo county, constituency and ward for Kobo-only members.
- Keeps the media CSV strictly as an emergency display fallback; an incomplete
  fallback result cannot replace the last complete durable combined tally.
- The live union is calculated in the background so dashboard response speed
  remains unchanged.

Deploy this voting-system backend. The six existing V3 dashboard services do
not need to be redeployed.
