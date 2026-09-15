V23.58 — MEMBERSHIP SUBMISSION FRESH RETRY

- Membership approval queries and writes now use a dedicated PostgreSQL
  connection rather than the shared pool used by dashboards and reports.
- A failed status lookup no longer blocks the form POST before it contacts the
  database. Pressing Submit always makes a fresh database attempt.
- If that fresh write genuinely fails, the form remains open and displays the
  actual database error instead of the stale generic reconnect message.

If V23.58 reports that DATABASE_URL is not configured, restore the Internal
Database URL in the voting service's Render environment and redeploy.
