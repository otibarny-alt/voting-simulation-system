V23.121 — MASTER REGISTER CONNECTION FALLBACK

Fixes dashboards remaining at the Kobo-only total (for example 48,010) when
MASTER_REGISTER_DATABASE_URL is blank.

Connection order
1. MASTER_REGISTER_DATABASE_URL, when configured.
2. DATABASE_URL, when the master_voters table was imported into the voting
   service's existing PostgreSQL database.

The six dashboard APIs now also return registered_voter_components containing:
- database_records
- kobo_records
- overlap_records
- kobo_only_records
- combined_unique_records

The combined formula is:
database_records + kobo_only_records

If the master register is in a separate Render database, set
MASTER_REGISTER_DATABASE_URL to that database's Internal Database URL before
redeploying. DATABASE_URL should continue to point to the voting system's
central PostgreSQL database.
