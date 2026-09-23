V23.93 — PROTECTED CLEAN TEST RESET

Admin Data Files now includes a protected Clean Testing Reset. It clears:
- all candidate applications through the Candidate Registration service
- local and central simulated votes
- voter admission/"already voted" state
- stream sessions and central terminal locks
- certified stream tallies
- opening and closing PDF repositories
- consumed one-time voting handoffs

It preserves membership data, master-register batches, election officials,
polling hierarchy/CSV files, credentials, and configuration.

Set SYSTEM_RESET_TOKEN to the same long random value on both Render services.
Keep CANDIDATE_PORTAL_BASE_URL set on the voting service. The administrator must
log in, type CLEAR TEST DATA exactly, and accept the final browser warning.
