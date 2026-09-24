V23.99 — REPORT REGISTERED-VOTER TOTALS

Closing reports now calculate Registered Voters from the same merged voter
records displayed in Admin > Voters Register.

- Counts unique National IDs for the report's polling station.
- Matches both polling-station machine keys and display labels.
- Uses county, constituency and ward to separate duplicate station names.
- Applies the same polling-station electorate to all six category reports.
- Caches the merged register for five minutes so six report sections do not
  repeatedly download and rebuild the register.
- Changes the report label to Registered Voters — Polling Station.

Existing archived PDF bytes retain their historical contents. Generate a new
closing report (or remove and regenerate a test report) to see the corrected
polling-station total.

This package includes all V23.98 terminal-session fixes.
