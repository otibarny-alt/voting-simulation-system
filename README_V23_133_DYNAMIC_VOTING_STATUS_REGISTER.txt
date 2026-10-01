V23.133 Dynamic Voter Participation Status
===========================================

The protected voters register now includes a Voting Status column linked to
the same central voter_status table updated by the Voting Terminal.

Behavior
--------
1. Each displayed voter is marked Voted or Not Voted.
2. Voted is shown in green; Not Voted is shown in amber.
3. The displayed register refreshes participation statuses every 15 seconds
   without reloading the complete membership register.
4. Summary counters show how many displayed voters have and have not voted.
5. CSV and printable PDF exports include the current voting status at the time
   the file is generated.
6. Statuses are retrieved in one bulk query for performance.
7. Only participation status is exposed. Candidate selections and ballot
   choices are never queried or displayed.
8. If the central status database is temporarily unavailable, the application
   falls back to locally confirmed vote records.

Serial numbers remain hidden from all voters-register outputs.
