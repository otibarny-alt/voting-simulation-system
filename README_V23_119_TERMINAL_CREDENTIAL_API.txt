V23.119 AUTHORITATIVE TERMINAL CREDENTIAL API

- Adds a protected server-to-server endpoint that resolves Entrance and Voting
  Terminal credentials from the voting system's current county_main.csv.
- The endpoint requires the existing shared AGENT_SSO_SECRET.
- Voter Verification V14.19 uses this endpoint so the login credentials always
  match the Polling-Station Terminal Assignments page.
