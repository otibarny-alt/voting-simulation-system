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


V23 — FORMAL MORNING OPENING / END-OF-DAY CLOSING WORKFLOW
TRAINING / SIMULATION ONLY.

Morning: select hierarchy, verify 0 pre-cast simulated votes, open and lock the terminal, print a separate Opening Report, and obtain candidate-agent signatures for all six elective positions.
End of day: close the locked stream, then print a separate Closing Results Report. It displays each configured candidate and the simulated votes recorded for that candidate in President, Governor, Senator, Woman Representative, MNA and MCA, followed by candidate-agent certification signatures.
Opening and closing reports open in separate tabs.
