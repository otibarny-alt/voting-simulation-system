V23.157 — UNIVERSAL ODM/UDA PARTY BRANDING

WHAT CHANGED
- Added the protected admin page /admin/party-branding.
- Added ODM and UDA as the first supported party profiles.
- The active profile is stored in shared PostgreSQL table app_party_branding.
- Logos, screen/report headers, primary colours, party name, abbreviation,
  slogan and visible membership wording change from one admin selection.
- New membership numbers use the active party prefix (ODM or UDA).
- Existing member numbers, votes, candidates, credentials and election records
  are never rewritten when branding changes.
- Added public read-only endpoint /api/party-branding for the candidate,
  verification and results services.

ADMIN USE
1. Sign in as administrator.
2. Open Admin Data Files > Party Branding.
3. Select ODM or UDA.
4. Click Apply Selected Party Universally.

CONNECTED SERVICES
- Deploy the companion candidate, verification and six dashboard packages.
- They use VOTING_SIMULATION_ADMIN_URL or SIMULATION_BASE_URL automatically.
- If neither already points at this voting service, set PARTY_BRANDING_API_URL
  to: https://YOUR-VOTING-SERVICE.onrender.com/api/party-branding

DATABASE
- Uses the existing voting service DATABASE_URL.
- The branding table is created automatically on first use.
- No manual schema migration is required.

ASSETS
- static/brand_odm_header.png
- static/brand_uda_header.png
