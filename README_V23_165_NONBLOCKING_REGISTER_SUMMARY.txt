V23.165 - Non-blocking full register summary

Emergency responsiveness correction after V23.164.

The county ribbon remains authoritative, but it no longer sends every filtered
National ID (sometimes more than 35,000 values) to the voting-status database.
It now:

- counts master-register members in PostgreSQL;
- counts distinct polling stations in PostgreSQL;
- retrieves only IDs that have actually voted;
- matches that much smaller voted-ID set against the selected geography;
- adds CSV-only Kobo members after duplicate-ID exclusion; and
- caches the completed summary for 30 seconds.

Browser refresh is reduced to once per 60 seconds. This prevents open register
tabs from exhausting the only Render web worker and blocking membership
registration, Admin Data Files, login and other pages.

No database migration is required. Deploy this package to the main voting
simulation service and restart that service after deployment.
