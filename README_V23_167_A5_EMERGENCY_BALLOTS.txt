V23.167 - A5 emergency paper ballots

Adds an administrator-only A5 backup ballot generator linked from Admin Data
Files.

Features
--------
- Filters through county, constituency, ward and one polling station.
- Generates all six election positions or one selected position.
- Uses only active, approved candidates returned by the Candidate Registration
  Portal; pending/rejected candidates are excluded.
- Enforces candidate scope: national, county, constituency or ward.
- Prints candidate number, passport photo, name, candidate ID, membership
  number and a clearly bordered voting box.
- Includes polling station, ward, constituency, county, station-specific ballot
  reference and presiding-officer stamp/signature line.
- Produces true A5 PDF pages and supports 1-50 master copies.
- Marks every page TRAINING / SIMULATION ONLY and instructs officials not to
  write voter names or National IDs on ballots.

Access
------
Admin Data Files -> A5 Emergency Paper Ballots

The generator requires CANDIDATE_PORTAL_BASE_URL to point to the deployed
Candidate Registration Portal. No database migration is required.
