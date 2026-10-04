V23.161 — EXACT VOTERS-REGISTER GEOGRAPHY TOTALS

- Dashboard electorate breakdown now groups the exact same deduplicated member
  rows displayed by the voters-register page.
- Applies the same county_main.csv geography enrichment before counting.
- Fixes members whose county is recovered from constituency, ward or polling
  station being missing from the dashboard county total.
- Rebuilds and persists the exact breakdown in the background after deployment.
- Immediate membership-change tally updates now use the same canonical geography.
- Designed to make Mombasa show 23,879 wherever the voters register shows 23,879.
- Polling-station stream totals remain sourced only from county_main.csv.
- No manual database migration is required.
