V23.198 - COUNTY BALLOT AVAILABILITY CHECKLIST

1. Added a County Ballot Availability Checklist to the filtered voter-totals
   web preview page.
2. Every county represented by the current filter has six status columns:
   President, Governor, Senator, Woman Representative, MNA and MCA.
3. Green cells show that a ballot exists and include the number of approved
   candidates. Red cells show that no approved candidates are available and
   the ballot is missing.
4. Presidential availability is national. The other five positions are
   checked against approved candidates in the individual county.
5. All counties are evaluated from one candidate-catalogue request to avoid
   slowing the voter-totals page with repeated network calls.
6. If candidate availability cannot be checked, voter totals still load and a
   clear checklist warning is displayed.
7. No database migration is required.
