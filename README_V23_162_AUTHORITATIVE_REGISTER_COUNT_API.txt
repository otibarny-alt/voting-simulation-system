V23.162 — AUTHORITATIVE VOTERS-REGISTER COUNT API

- Adds authenticated GET /api/voters-register/count for all six dashboards.
- Runs the same combined_voters_register filter and geography enrichment used
  by the protected voters-register page.
- Returns one exact count for county, constituency, ward or polling station.
- Returns HTTP 503 if the register cannot be counted; no guessed/stale total is
  supplied to dashboards.
- Resolves one-voter and other small differences caused by independent snapshots.
- Uses the existing X-Dashboard-Key / DASHBOARD_API_KEY security.
- No database migration is required.
