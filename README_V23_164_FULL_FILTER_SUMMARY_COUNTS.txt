V23.164 - Full-filter register summary counts

The voters-register ribbon now calculates all summary figures from the entire
filtered register, never from only the 500 rows displayed in the browser.

For a county filter such as Laikipia, it shows:

  35,765 members in X polling stations in Laikipia County.
  Y voted - Z not voted

where X is the number of distinct polling stations represented by all filtered
members, Y is the number of those members recorded as voted for the active
election, and Z equals total members minus Y.

The same rule applies automatically at county, constituency, ward and polling
station levels. Full-filter voting totals refresh every 30 seconds. The visible
table remains limited to 500 records to prevent Render 502 gateway errors.

No database migration is required. Deploy this voting-system package after
V23.163. The six authoritative-count dashboards do not require another code
change.
