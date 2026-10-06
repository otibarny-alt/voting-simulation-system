V23.174 ADMIN TERMINAL RESET BRIDGE

- Adds Reset Verification & Voting Terminals to Admin Data Files.
- Uses the existing Voting Admin Data Files login; no second Verification
  administrator login is required.
- Lists active Verification and paired Voting Terminal status by station.
- Administrator reset releases both roles for the selected station.
- Uses the shared AGENT_SSO_SECRET for authenticated server-to-server access.
- If Verification is unavailable, no session is changed and a retry message
  is displayed.

Deploy together with Verification V14.33.
