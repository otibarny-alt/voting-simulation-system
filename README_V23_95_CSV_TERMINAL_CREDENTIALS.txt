V23.95 — CSV VOTING TERMINAL ACCESS

The voting service now accepts only a signed handoff issued after a successful
Voting Terminal ID/password login on the verifier service. The terminal is
restricted to its county, constituency, ward, polling station, and stream from
county_main.csv.

Public entry:
- /terminal-login redirects the device to the Voting Terminal login.
- Unauthenticated voting pages also redirect to that login.

Compatibility:
- Existing signed-handoff environment variable names are retained.
- Set the same AGENT_SSO_SECRET value on both Render services.
- Set VOTER_VERIFICATION_BASE_URL to the verifier service URL.

Deploy verifier V14.12 before this package.
