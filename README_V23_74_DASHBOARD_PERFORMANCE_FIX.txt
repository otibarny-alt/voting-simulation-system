V23.74 — PRESIDENTIAL AND MCA DASHBOARD PERFORMANCE FIX

This release fixes the long waits and HTTP 502 responses seen on the
Presidential and Member of County Assembly results dashboards.

Changes:
- The central results feed now requests the full candidate catalogue once.
  MCA no longer makes one remote candidate request per ward represented in
  vote events.
- Kobo membership CSV loading is single-flight. Concurrent dashboard requests
  share one download/parse instead of multiplying memory use on Render.
- All six central result payloads are cached for 120 seconds by default.
- Existing vote totals, registered-voter filtering, stream states, and all
  geographic result filters are unchanged.

Deploy this voting-system package first. Then deploy the matching Presidential
V12 and MCA V5 dashboard packages.
