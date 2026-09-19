V23.79 — RECRUITED AGENT ADMINISTRATION

The Agent Recruitment Portal card on Admin Data Files now includes a protected
Manage Recruited Agents link. Deploy the companion Voter Verification V14
package as well; that service owns activated election-agent accounts.

Administrators can view each activated recruited agent, assigned polling
station and stream, activate or deactivate access, and reassign an agent to a
valid stream from county_main.csv. The verifier enforces the new status and
assignment on an already signed-in session.

No new Render environment variable is required. VOTER_VERIFICATION_BASE_URL
must continue to point to the deployed voter-verification service.
