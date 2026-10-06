V23.184 FILTERED TERMINAL RESET PAGE

Adds cascading County, Constituency, Ward and Polling Station filters to the
administrator-only Verification and Voting Terminal Reset page.

The page no longer requests or displays a nationwide active-terminal list on
initial load. An administrator must select a county first. More specific
filters can then narrow the active terminals to constituency, ward or polling
station. Selected filters remain applied after resetting a station.

The filter hierarchy comes from the deployed county_main.csv assignments.
No database migration is required.
