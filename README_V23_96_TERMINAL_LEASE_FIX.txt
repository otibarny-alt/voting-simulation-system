V23.96 — VOTING TERMINAL LEASE FIX

- Confirms the verifier reservation when the signed voting handoff is consumed.
- Refreshes the reservation at most once per minute while the terminal is used.
- Adds /terminal-logout to release the Voting Terminal ID immediately.
- Rejects a voting session whose terminal reservation has been replaced.

Deploy Verifier V14.13 first, then deploy this voting package.
