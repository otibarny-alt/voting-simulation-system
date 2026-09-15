V23.52 — LIVE RESULTS STREAM-STATE FIX

What was corrected
------------------
All six live dashboard feeds now keep a polling-station stream OPEN after a
terminal/device reservation is released. Releasing or resetting a terminal is
not the same operation as formally closing the voting stream. The stream stays
OPEN from its central locked_at/opening time until central closed_at is set.

Feeds corrected centrally
-------------------------
- /api/dashboard/president
- /api/dashboard/governor
- /api/dashboard/senator
- /api/dashboard/woman-rep (and aliases)
- /api/dashboard/mna
- /api/dashboard/mca

Deployment
----------
Deploy this package to the voting-simulation-system Render service. Keep the
existing environment variables and persistent PostgreSQL DATABASE_URL.

