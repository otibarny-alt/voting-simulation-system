V23.55 — CERTIFIED MULTI-STATION CONSOLIDATION

Problem corrected
-----------------
Polling-station stream PDFs were correct, but higher-level totals were being
calculated from raw live vote events. Open streams could therefore enter a
supposed final tally, and a PDF had no machine-readable candidate totals to
combine reliably.

New consolidation process
-------------------------
1. A stream must be formally closed.
2. Depositing each category PDF also stores an anonymous structured candidate
   tally for that stream.
3. Consolidation reads certified tallies only. Reports created before V23.55
   are backfilled from durable vote events only where the central stream record
   is formally closed.
4. Duplicate protection now uses the complete geographic key: election date,
   category, county, constituency, ward, polling station and stream.

Correct result scopes
---------------------
- President: National
- Governor, Senator, Women Representative: County
- MNA: County + Constituency
- MCA: County + Constituency + Ward

The Admin Data Files page now labels the report Certified Consolidated Final
Tallies. It lists every candidate, votes, percentage, rank, total valid votes
and the number of closed streams combined. Existing winner/runner-up CSV and
print functions remain available.
