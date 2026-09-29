V23.126 — AUTHORITATIVE 40,581-MEMBER REGISTER

Authoritative calculation:

  36,800 active PostgreSQL master-register records
  + Kobo membership CSV National IDs absent from PostgreSQL
  = 40,581 unique members across 63 polling stations

- Reads the earlier membership_registration.csv stored in Kobo form media.
- Does not use live Kobo form submissions for results-dashboard voter totals.
- Normalizes and deduplicates Kobo National IDs.
- When the same ID exists in both sources, the PostgreSQL master record wins
  and the Kobo row is not counted a second time.
- Publishes the PostgreSQL count first while the Kobo CSV downloads, then
  refreshes all six result dashboards with the complete unique union.
- Preserves the complete union in the shared durable tally cache.

Deploy this voting-system backend only. The existing V3 result dashboards are
compatible and do not require redeployment.
