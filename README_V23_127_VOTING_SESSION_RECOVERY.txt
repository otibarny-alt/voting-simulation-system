V23.127 — VOTING TERMINAL SESSION RECOVERY

- Fixes /start returning a bare “Authenticated Voting Terminal access is
  required” response after the voting terminal had already logged in.
- Stores a signed, HTTP-only recovery copy of the authenticated voting-terminal
  handoff so a lost Flask session can be restored during voter submission.
- The recovery cookie contains the same station/stream handoff, expires with
  the configured agent session and cannot be modified without invalidation.
- Terminal logout, release and replacement clear both the Flask session and
  the recovery cookie.
- An unverified voter now receives:
  “VOTING NOT ALLOWED: This voter has not been verified at the entrance.
  Please complete entrance verification before proceeding.”
- The station lock, voting sequence and entrance-approval requirement remain
  enforced.

Deploy this voting-system backend only. No dashboard deployment is required.
