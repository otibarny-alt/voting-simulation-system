V23.80 — AGENT-AUTHENTICATED VOTING ACCESS

The Voting System no longer permits an unauthenticated browser to open or use
a voting stream. An active recruited agent must first sign in to the Voter
Verification service and use Open Assigned Voting System.

Security controls:
- five-minute signed handoff from Voter Verification;
- each handoff token can be consumed only once;
- the Voting System session is locked to the agent's assigned station/stream;
- manual station and stream selection is removed for the agent;
- opening, voting, closing and terminal reset require agent authentication;
- the existing central device/stream lock remains in force;
- agent access expires after 12 hours by default.

RENDER CONFIGURATION (REQUIRED)
Set AGENT_SSO_SECRET to the same long random value on both the Voting System
and Voter Verification services. Never use different values.

The Voting System also needs:
VOTER_VERIFICATION_BASE_URL=https://odm-member-photo-verifier.onrender.com

Deploy the companion Voter Verification V14.1 package before this package.
