V23.68 SERIAL-NUMBER VOTING SEARCH

- The voting terminal now searches membership records using serial_no.
- Live Kobo uses MEMBERSHIP_SERIAL_FIELD (default: basics/serial_no).
- membership_registration.csv accepts serial_no, serial_number, or serial.
- The matched National ID remains the internal key for entrance approval,
  ballot sessions, already-voted checks, vote persistence, and audit history.

If the Kobo question is not named basics/serial_no, set
MEMBERSHIP_SERIAL_FIELD in Render to its exact deployed XLSForm question path.
