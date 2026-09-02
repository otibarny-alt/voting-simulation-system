2027 TRAINING E-BALLOT PROTOTYPE V1

NON-BINDING TRAINING / SIMULATION ONLY.

Flow:
Demo verification -> President -> Governor -> Senator -> Woman Rep -> MNA -> MCA
-> Review -> Save simulated ballot -> Simulated tally dashboard.

Candidate cards currently use Candidate 1..N placeholders and numbered photo boxes.
The six simulated selections are stored only in a local demo SQLite database.

This package is deliberately not connected to the production voter-verification
system and must not be used to record or tally official votes.

Render:
Build: pip install -r requirements.txt
Start: gunicorn app:app
Set FLASK_SECRET_KEY to a random secret.


V2 CASCADING ELECTORAL UNITS
- Bundles county_main.csv.
- Replaces manual County, Constituency, Ward, Polling Station and Stream typing
  with cascading dropdowns.
- Hierarchy:
  County -> Constituency -> Ward -> Polling Station -> Stream.
- Uses list_name and parent keys from county_main.csv.
- Includes all 47 counties and the polling-station-stream rows in that file.
- No new Render environment variable is required.


V3 SELECTION FEEDBACK
- Selected candidate card changes to a light highlighted background.
- Selected card rises/pops out slightly.
- Stronger shadow and border make the choice obvious.
- A visible "✓ SELECTED" badge appears on the chosen candidate.
- Text confirmation announces the selected candidate.
- Only one candidate can remain selected because the ballot uses radio buttons.


V4 REVIEW VOTER ID
- The review screen now prominently displays the demo voter's ID number.
- The voter is asked to confirm the ID before saving the simulated ballot set.
- The ID is read from the current session and is not manually re-entered on review.


V5 TERMINAL / STREAM LOCK
- The electoral hierarchy is selected only once per computer/browser.
- The chosen County, Constituency, Ward, Polling Station and Stream are stored
  locally in that browser as the terminal assignment.
- Subsequent voters only enter their voter ID.
- Clicking "Next voter on this computer" returns to the ID entry screen while
  retaining the same voting stream.
- A "Change voting stream" control is available if the computer is moved to
  another room/stream.
- The assignment survives ordinary page refreshes and browser restarts because
  it is kept in browser local storage.
- Clearing browser/site data will clear the terminal assignment.
- No new Render environment variables are required.


V6 SUBSEQUENT VOTER SUBMISSION FIX
- Fixes the issue where the second/subsequent voter could enter an ID but the
  Start button appeared not to respond.
- Cause: hidden terminal setup dropdowns still had HTML 'required' validation.
  On later voters those dropdowns were empty on page load, so the browser
  silently blocked form submission even though the saved stream was valid.
- Terminal setup completeness is now validated only when the stream is first
  locked.
- Once a terminal is locked, its setup dropdowns are disabled and the stored
  electoral-unit values are submitted through hidden fields.
- Subsequent voters can now enter only their voter ID and continue directly to
  the six training ballots.


V7 NO DOUBLE VOTING — TRAINING SIMULATION
- A voter ID that already has a saved simulated ballot set is blocked from
  starting another six-ballot session.
- The check happens when the voter ID is entered and is repeated again before
  the simulated selections are written.
- A clear red warning is shown for duplicate voter IDs.
- The same ID remains blocked across different terminals as long as those
  terminals use the same persistent demo database.
- Resetting all simulated votes from the tally dashboard clears this training
  restriction because the demo vote records are deleted.


V8 SHOW ZERO-VOTE CANDIDATES
- The simulated tally dashboard now lists every configured candidate in every
  election category, even when that candidate has received 0 votes.
- President shows Candidate 1 through Candidate 10.
- Governor, Senator, Woman Rep, MNA and MCA show all candidates configured in
  the prototype.
- Vote counts update automatically as simulated ballots are saved.


V9 RANKED TALLIES
- Candidates in every election section are sorted from highest votes to lowest.
- A Rank column is shown.
- Candidates with equal vote totals share the same rank.
- Candidate slot number is used only to keep tied candidates in a stable order.
- Zero-vote candidates remain visible and are ranked after candidates with votes.


V10 DUPLICATE-VOTER POLLING-STATION MESSAGE
- When a previously used voter ID is entered, the warning now identifies the
  polling station recorded with that simulated ballot.
- Example:
  "Voter ID 10703460 has already voted at RATTA PRIMARY SCHOOL polling station
  and cannot vote again."


V11 — REGISTERED VOTER SUMMARIES
Uses bundled agents_login.csv. total_registered_voters is read by poll_station_name (stream).
At the end of EACH elective-position tally: Total Votes Cast, Registered Voters per stream,
Registered Voters per polling station, and Votes Not Cast. Detailed stream and station tables
are also shown. Polling-station registered totals include all streams belonging to the station.
TRAINING / SIMULATION ONLY.


V12 — A4 PRINT BUTTONS
- Every elective-position tally has its own Print button.
- Clicking it opens the browser/operating-system print dialog for the connected/default printer.
- Only that elective-position section is included in the print job.
- Print CSS requests A4 portrait paper and removes dashboard navigation/buttons from the printed page.
- The browser controls the actual printer selection; a normal web application cannot silently force a specific connected printer without browser/OS or kiosk-print configuration.
TRAINING / SIMULATION ONLY.


V13 — CANDIDATE AGENT SIGNATURE LINES
- At the end of every elective-position printout, a Candidate Agents' Certification section is added.
- One signature row is created for every candidate listed in that tally.
- Columns: Candidate, Agent Name, Signature, Date / Time.
- Includes blank Polling Station and Stream confirmation lines.
- Certification text states that signatories confirm the printout is a true copy of the simulated results for that polling station stream.
- Designed to print as part of the same A4 tally printout.
TRAINING / SIMULATION ONLY.


V14 — PRESIDING / RETURNING OFFICER SIGNATURES
- Adds an Election Officials' Certification area to every elective-position printout.
- Presiding Officer: Name, Signature, Date/Time.
- Returning Officer: Name, Signature, Date/Time.
- Appears after the candidate-agent certification section.
TRAINING / SIMULATION ONLY.


V15 — POLLING STATION STREAM COUNT
- The "Registered Voters / Votes Cast Per Polling Station" table now includes
  "No. of Streams".
- This count shows how many polling station streams contribute to the
  Registered Voters total for that polling station.
- The count is derived from county_main.csv using the same station-to-stream
  relationship used to calculate registered voters.
TRAINING / SIMULATION ONLY.


V16 — PRE-OPENING ZERO-VOTE + OPEN/CLOSE REPORT
- Each stream must pass a 0 pre-cast simulated-votes check before simulated voting can start.
- The actual opening and closing timestamps are recorded on the same-day stream session.
- A printable A4 report shows the clean-system check, date, scheduled hours, actual timestamps,
  schedule comparison, candidate-agent signature lines, Presiding Officer and Returning Officer.
- Set the required hours in Render Environment:
  VOTING_OPEN_TIME=HH:MM
  VOTING_CLOSE_TIME=HH:MM
  No legal/official hours are assumed by the prototype; enter the hours required for your training exercise.
TRAINING / SIMULATION ONLY.


V17 — CASCADING STREAM CONTROL FROM county_main.csv
The Pre-Opening / Closing Control page no longer requires manual typing of electoral units.
It uses the existing /api/hierarchy endpoint backed by county_main.csv:
County -> Constituency -> Ward -> Polling Station -> Stream.
Each selection filters the next dropdown and the selected values are submitted to the
existing zero-precast-vote/open-stream procedure.
TRAINING / SIMULATION ONLY.


V18 — SIX ELECTIVE-POSITION AGENT SIGNATURES
The printable stream opening/closing report now provides candidate-agent signature rows
for all six elective positions because the same candidate may have a different agent
at each polling-station stream.

Opening certification sections:
- President: Candidate 1–10
- Governor: Candidate 1–6
- Senator: Candidate 1–6
- Woman Representative: Candidate 1–6
- MNA: Candidate 1–6
- MCA: Candidate 1–6

Closing certification repeats the same six elective-position agent signature sections.
Each row has Candidate, Agent Name, Signature, and Date/Time.
Presiding Officer and Returning Officer signature lines are included separately for
both opening and closing.

The report may span multiple A4 pages so that each agent has adequate signing space.
TRAINING / SIMULATION ONLY.


V19 — DYNAMIC PRINTED REPORT HEADER
A dynamic header/logo image can now be displayed on all printed reports using a Render
environment variable.

Add this environment variable in Render:
REPORT_HEADER_IMAGE_URL=https://your-public-image-url.example/header.png

The image is NOT hard-coded into the application. The application reads the URL at runtime.
Changing REPORT_HEADER_IMAGE_URL changes the printed report header without editing the code.

The dynamic header appears on:
- Voting Stream Opening / Closing Report
- President tally printout
- Governor tally printout
- Senator tally printout
- Woman Representative tally printout
- MNA tally printout
- MCA tally printout

Important:
- The value must be a direct, publicly accessible image URL (PNG/JPG/WebP).
- Do not use a Google Drive page/share URL unless it resolves directly to the image.
- If REPORT_HEADER_IMAGE_URL is empty, no header image is printed.
TRAINING / SIMULATION ONLY.


V20 — BUNDLED REPORT HEADER IMAGE
The supplied ODM Vote Count and Transmission header image is now included inside:
static/odm_report_header.png

Recommended Render environment variable:
REPORT_HEADER_IMAGE_URL=/static/odm_report_header.png

The application also defaults automatically to that local path if the variable is omitted.

Advantages:
- No dependency on GitHub raw URLs.
- Works even when the GitHub repository is private.
- Header is served directly by the Render web application.
- Changing the environment variable later can still point to a different public image if desired.

The header appears on all printed reports supported by V19:
- Voting Stream Opening / Closing Report
- President tally
- Governor tally
- Senator tally
- Woman Representative tally
- MNA tally
- MCA tally

TRAINING / SIMULATION ONLY.


V21 — OPEN/CLOSE REPORT IN NEW TAB
The "View / Print Opening & Closing Report" link now opens the report in a separate
browser tab using target="_blank" and rel="noopener".
The Voting Stream Control page remains open in the original tab, so after printing or
reviewing the report the operator can simply close the report tab instead of using Back.
TRAINING / SIMULATION ONLY.


V22 — HARD LOCK VOTING TERMINAL TO PRE-OPENED STREAM
After the pre-voting zero-vote verification opens a polling-station stream, that browser/device
is locked to the selected County, Constituency, Ward, Polling Station and Stream for that day.

Security/flow changes:
- The lock is stored in a signed, HttpOnly browser cookie.
- Ballot start ignores any manually posted geography and uses only the signed terminal lock.
- Ballot casting re-checks that the session geography still matches the signed terminal lock.
- The stream-control page no longer offers a second manual stream-opening form after locking.
- The voter screen displays the locked Polling Station and Stream.
- The previous "Change voting stream" workflow is no longer available during ballot casting.
- Closing the stream does not permit further voters in that stream.

This is a per-browser/device training-terminal lock. Clearing browser cookies or using another
browser/device creates a different terminal context; for a stronger multi-device simulation,
terminal identity and locks should be stored centrally in a persistent simulation database.
TRAINING / SIMULATION ONLY.


V22.1 — CONTROLLED TERMINAL RESET
Built directly from stable V22.

Adds "Reset Terminal for New Stream" on the Stream Control page.

Reset is allowed only when:
1. No simulated ballot has yet been cast in the currently locked polling-station stream; OR
2. The currently locked stream has been formally closed.

Reset is blocked if the stream is still open and any simulated votes already exist.

When reset succeeds:
- signed terminal-lock cookie is removed
- current Flask voting session is cleared
- operator returns to station/stream selection
- a different County / Constituency / Ward / Polling Station / Stream can be chosen

The working V22 ballot and stream-lock flow is otherwise unchanged.
TRAINING / SIMULATION ONLY.


V22.2 — ODM MEMBERSHIP PHOTO VERIFICATION GATE
Built from stable V22.1 training simulation.

Before the simulated ballot begins:
- Officer enters National ID.
- App queries the ODM Membership Registration Database.
- The matching member's ID Photo and Passport Photo are displayed side by side.
- Member name, membership number and membership polling station are also displayed when available.
- Officer must click "Identity Confirmed — Continue to Simulation Ballot".
- A member not found in the ODM Membership Registration Database cannot proceed.
- Existing duplicate-voter and locked-stream checks remain in place.

Membership form fields used:
basics/national_id_no
basics/id_photo
basics/passport_photo
members_particulars/odm_membership_no
members_particulars/first_name
members_particulars/other_names
members_particulars/surname
electorals_units/poll_station_label or selected_poll_station1

Required Render environment variables:
KOBO_BASE_URL=https://kf.kobotoolbox.org
MEMBERSHIP_ASSET_UID=<UID OF MEMBERSHIP RECRUITMENT PORTAL>
KOBO_API_TOKEN=<YOUR EXISTING KOBO TOKEN>

Photos are proxied server-side so the membership database API token is not exposed to the browser.

IMPORTANT: This package connects membership verification only to the NON-BINDING TRAINING /
SIMULATION ballot. It is not designed or provided for recording binding political votes.


V22.3 — ODM POLLING-STATION MATCH GATE
Built from V22.2.

The voter can proceed to the training/simulation ballot only when the polling station stored
in the ODM Membership Registration Database matches the polling station locked on the voting terminal.

Membership fields used for station matching, in priority order:
- electorals_units/selected_poll_station1
- particulars_confirmation/selected_poll_station1_confirmation
- stored_particulars_confirmed/selected_poll_station1_calculation
- stored_particulars_confirmed/selected_poll_station1_confirmed

Display label:
- electorals_units/poll_station_label

The comparison normalizes capitalization, spaces, punctuation, and underscores so values such as:
MWENA PRIMARY SCHOOL
and
mwena_primary_school
are treated as the same station.

If the stations match:
- ID Photo and Passport Photo are shown
- green POLLING STATION MATCH CONFIRMED message appears
- officer can confirm identity and continue to the simulation ballot

If they do not match, or no membership polling station is available:
- red POLLING STATION MISMATCH message appears
- both station values are displayed
- Continue button is disabled
- voter cannot enter the simulation ballot

The server re-checks the station-match flag at /membership/confirm so this is not only a browser/UI restriction.

TRAINING / SIMULATION ONLY.


V22.4 — TALLY PRINT DATE/TIME/GPS
Built from V22.3.

Each printed simulated tally report now records:
- Report date
- Report time (Africa/Nairobi / Kenya time)
- GPS latitude
- GPS longitude
- Browser-reported GPS accuracy
- GPS capture status

The timestamp and GPS are captured when the operator clicks the individual Print button
for President, Governor, Senator, Woman Rep, MNA or MCA.

GPS uses the browser Geolocation API and therefore requires the user/device to allow Location
permission for the Render site. If permission is denied or the device/browser cannot obtain
a position, the report clearly prints that GPS was not captured rather than inventing a location.

TRAINING / SIMULATION ONLY.


V22.5 — OPENING REPORT ONLY
The stream report has been simplified to contain only morning opening details.

Included:
- Polling Station
- Stream
- Date
- 0 pre-cast votes verification
- Scheduled opening time
- Actual opening timestamp
- Opening time check
- Candidate-agent opening verification/signatures
- Election-official opening signatures
- Dynamic report header

Removed from this report:
- Scheduled closing
- Actual closing timestamp
- Closing check
- Distinct simulated voters recorded

Closing information remains in the final vote-count/tally reports.
TRAINING / SIMULATION ONLY.


V22.6 — AUTOMATIC DATE/TIME/GPS CAPTURE FIX
Built from V22.5.

Changes:
- Date and Kenya time are populated automatically when the tally dashboard loads.
- GPS is requested automatically when the tally dashboard loads.
- GPS is requested again immediately before each individual tally is printed.
- A short render delay is used before opening print preview so the freshly captured values
  are visible on the printed report.
- All tally sections receive the same captured page-load GPS value.
- If browser Location permission is denied, the report now states:
  "Location permission denied — allow Location for this site".
- If GPS cannot be obtained, the report gives the specific browser status instead of remaining
  indefinitely at "Waiting for print".

On Render/HTTPS, browser geolocation should work when Location permission is granted.
TRAINING / SIMULATION ONLY.


V22.7 — MORNING OPENING CERTIFICATION ONLY
- Removed Closing Certification — Candidate Agents from the morning Opening Report only.
- Removed Closing — Election Officials from the morning Opening Report.
- Opening Certification — Candidate Agents remains.
- Opening — Election Officials remains.
- Closing candidate-agent certification remains in the final tally reports.
- V22.6 date/time/GPS tally-report changes are retained.
TRAINING / SIMULATION ONLY.

V22.8 — OPENING STATION GPS
Morning Opening Report now captures current device GPS: latitude, longitude, accuracy and status.
Location permission must be allowed. TRAINING / SIMULATION ONLY.


V22.9 — PERSISTED OPENING GPS FIX
The previous opening-report GPS script was not guaranteed to execute because the report template
did not contain a closing </body> tag. V22.9 changes the workflow so GPS is captured BEFORE the
stream is opened and stored with the stream-opening record.

New opening workflow:
1. Select County / Constituency / Ward / Polling Station / Stream.
2. Click "Capture GPS, Verify 0 Pre-Cast Votes & Open Stream".
3. Browser asks for Location permission.
4. Stream opens only after a current GPS fix is obtained.
5. Latitude, longitude and browser-reported accuracy are stored in stream_sessions.
6. The morning opening report reads the stored opening GPS from the database, so opening a new
   report tab does not need to obtain GPS again.

Existing stream records opened before V22.9 will not contain stored opening GPS. For those records,
the report attempts a browser GPS fallback and labels it clearly as a current-device fallback.

TRAINING / SIMULATION ONLY.


V22.10 — CANDIDATE REGISTRATION PORTAL INTEGRATION
==================================================
TRAINING / SIMULATION ONLY — NOT FOR OFFICIAL OR BINDING ELECTION USE.

Add this Render environment variable to the TRAINING BALLOT web service:
CANDIDATE_PORTAL_BASE_URL=https://your-candidate-registration-service.onrender.com

Do not add a trailing slash.

Candidate scope:
President = National
Governor = County
Senator = County
Woman Representative = County
MNA = Constituency
MCA = Ward

The training ballot sends its locked County, Constituency and Ward to the Candidate
Registration Portal API and receives only active candidates applicable to that location.

The ballot displays candidate photo, full name, Candidate ID, membership number and bio.
Simulated vote records now store stable Candidate ID and Candidate Name snapshots so
later candidate reordering does not change the identity of previously cast simulation votes.

If candidate data is unavailable, the ballot blocks the affected simulated position instead
of falling back to placeholder candidates.


V22.11 — SELECTED CANDIDATE PHOTOS ON REVIEW SCREEN
===================================================
TRAINING / SIMULATION ONLY.

The final review screen now re-loads each selected candidate profile from the
Candidate Registration Portal and displays a large candidate photograph for:
President, Governor, Senator, Woman Representative, MNA and MCA.

The photograph is displayed together with the election position, candidate name
and Candidate ID. Each selection has a clearly labelled Change button.

This visual review is intended to make confirmation easier for users who may have
difficulty reading candidate names. Candidate photos supplement the names and do
not replace the existing selection confirmation controls.
