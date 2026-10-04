V23.163 - Fast county register and authoritative dashboard totals

This release fixes the two related county-filter failures:

1. The protected voters register now limits the browser page to 500 records.
   The complete filtered selection remains available through CSV/PDF export.
   This prevents a large county from exhausting the Render web worker and
   producing a 502 Bad Gateway response.

2. GET /api/voters-register/count no longer renders and sorts the complete
   register to obtain one number. It uses a PostgreSQL COUNT plus only the
   filtered legacy CSV members whose National IDs are absent from PostgreSQL.
   The same five-second coalescing cache serves simultaneous dashboard calls.

3. PostgreSQL remains authoritative for duplicate National IDs. The displayed
   total still represents the master register plus CSV-only Kobo members.

Deployment
----------
Deploy this voting-system package first. The six dashboards from the V23.162
authoritative-count bundle require no further code change. Confirm every
dashboard has the same SIMULATION_BASE_URL and SIMULATION_DASHBOARD_API_KEY as
this voting service, then redeploy/restart the dashboards.

No database migration is required.
