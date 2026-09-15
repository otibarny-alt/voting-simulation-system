V23.54 — PRESIDENTIAL RESULTS ENDPOINT TIMEOUT FIX

The live result feeds now initialize only:
- simulation_dashboard_vote_events
- simulation_terminal_locks

They no longer initialize the PDF repository, membership requests, voter access
tables, or unrelated indexes before answering a dashboard request. Unnecessary
database sorting was also removed from the aggregate query.

This directly fixes the /api/dashboard/president read timeout shown by the
Presidential Results Dashboard and improves the same source endpoint used by
the other five live result dashboards.

Deploy this ZIP to voting-simulation-system. The Presidential Dashboard V6 can
remain deployed; no environment-variable changes are required.
