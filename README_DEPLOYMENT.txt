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
