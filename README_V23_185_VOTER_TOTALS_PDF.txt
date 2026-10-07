V23.185 ADMIN VOTER TOTALS PDF

Adds a protected "Download Voter Totals PDF" link under Admin Data Files.

The report can group registered-voter totals by county, constituency, ward or
polling station. It uses the same deduplicated PostgreSQL master register plus
Kobo/legacy-only membership records as the voters register; duplicate National
IDs use the master record.

To keep large reports reliable:
- County totals may be generated nationally.
- Constituency totals require a county.
- Ward totals require a county and constituency.
- Polling-station totals require a county, constituency and ward.

The PDF includes ODM branding, selected scope, geographic totals, grand total,
source reconciliation and page numbers. No database migration is required.
