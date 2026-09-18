V23.76 — AUTOMATIC OPENING REPORT REPOSITORY

- Every successful voting-stream opening automatically generates and deposits
  one formatted opening-report PDF in shared PostgreSQL.
- Deposits run after the stream is safely opened, so repository or candidate
  service delays do not block voting operations.
- Deposits are idempotent: retries update the same date/geography/station/stream
  record rather than creating duplicates.
- Viewing an opening report triggers a safe background repair retry if the
  first automatic deposit was interrupted.
- Admin Data Files now links to the Opening Report Repository and the existing
  Closing Tally Repository.
- The opening repository supports county, constituency, ward, polling-station
  and stream filters, PDF viewing/downloading, pagination and admin deletion.

Deploy this package to the main Voting Simulation System service only.
