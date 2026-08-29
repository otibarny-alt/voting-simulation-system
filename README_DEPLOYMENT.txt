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
