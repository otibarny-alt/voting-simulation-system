V23.120 — COMBINED DASHBOARD REGISTER TOTALS

All six result dashboards now calculate Total Registered Voters from the
deduplicated union of:

1. Active voters in the PostgreSQL master register database; and
2. Members in the Kobo membership registration CSV.

National ID is the deduplication key. When the same ID exists in both sources,
the database record is authoritative and the voter is counted only once.

The combined total and county/constituency/ward breakdown are cached for five
minutes to keep the results dashboards responsive. No dashboard template or
deployment environment-variable change is required.
