V23.81 — DEDICATED VOTING TERMINAL

When Voting System access is required, the browser is now redirected to the
Voter Verification service's dedicated Voting Terminal login. It is no longer
opened from inside an active Verification Terminal session.

Deploy together with Voter Verification V14.4. The same AGENT_SSO_SECRET must
remain configured on both Render services. The central entrance-approval check
for each voter remains mandatory and unchanged.
