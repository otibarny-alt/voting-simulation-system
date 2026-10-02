V23.144 - Voting Database URL Fallback

The Voting service now selects its shared PostgreSQL database in this order:

1. VOTING_DATABASE_URL
2. MASTER_REGISTER_DATABASE_URL
3. DATABASE_URL

This fixes the /agent-access failure after a successful Voting Terminal login
when the old DATABASE_URL contains an expired or unresolvable Render hostname.
The selection applies consistently to handoffs, stream locks, preserved votes,
reports and dashboards so login does not succeed only to fail on the next page.

The raw white database-error response has been replaced by a branded recovery
page without exposing the database hostname.
