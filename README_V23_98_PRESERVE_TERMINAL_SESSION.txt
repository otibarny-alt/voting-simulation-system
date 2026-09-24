V23.98 — PRESERVE AUTHENTICATED VOTING TERMINAL

Fixes the error:
"Authenticated Voting Terminal access is required for this voting-stream action."

Cause:
The voter lookup handler cleared the complete Flask session after successful
authentication. That also deleted the signed Voting Terminal handoff before
membership confirmation could open the ballot.

Fix:
- Voter resets now remove only voter-specific private data.
- Voting Terminal authentication and lease state remain intact.
- Applied throughout lookup, confirmation, cancellation, duplicate handling,
  ballot/review/casting, and terminal reset.
- Terminal logout and full administrator test-data reset still clear the full
  session intentionally.

This package builds on V23.97. Keep Verifier V14.14 deployed.
