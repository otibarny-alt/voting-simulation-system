V23.173 PAPER TALLY 500 FIX

Fixes the HTTP 500 error at /stream/paper-tally after a voting stream closes.

Cause:
The electronic-vote lookup found the exact closed session, correctly skipped
the legacy recovery query, and then referenced the legacy result variable even
though that fallback had not run.

Correction:
- Initialize the fallback result before the exact-session lookup.
- Preserve exact-session electronic votes for the combined tally.
- Display a safe automatic-retry page if the tally database is temporarily
  unavailable instead of showing a raw white HTTP 500 screen.
- No recorded electronic or paper vote data is changed or deleted.
- No database migration is required.
