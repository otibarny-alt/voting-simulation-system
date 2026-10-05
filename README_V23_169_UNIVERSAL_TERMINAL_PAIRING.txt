V23.169 — UNIVERSAL TERMINAL PAIRING COMPANION

This voting package works with Verification System V14.29.

- Voting access is handed off only after station credentials and the short-lived
  pairing code have been validated by the verification service.
- The existing voting-terminal heartbeat continues checking the paired Entrance
  Terminal through the server.
- When the Entrance Terminal is offline, the voting interface pauses with a
  clear recovery message instead of showing a GPS or white-screen failure.
- Browser and operating-system GPS behavior does not control voting access.

Deploy this voting package first and Verification System V14.29 second. Both
services must retain the same AGENT_SSO_SECRET, central database and ELECTION_ID.
