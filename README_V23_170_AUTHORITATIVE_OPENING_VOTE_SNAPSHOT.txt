V23.170 — AUTHORITATIVE OPENING VOTE SNAPSHOT

Fixes opening reports that always displayed "0 — VERIFIED CLEAN" even when
central records showed that voters had already completed ballots.

Changes
- The stream-opening process counts distinct completed voters from both the
  local terminal database and authoritative PostgreSQL records.
- Central anonymous ballot events and shared voter-status/admission records are
  reconciled; the larger confirmed count is used.
- The count is stored as an immutable opening-time snapshot in the stream row.
- HTML, printable PDF, emailed PDF and repository PDF all use that snapshot.
- A zero count prints "VERIFIED CLEAN".
- A non-zero count prints "PRE-EXISTING VOTES RECORDED — NOT A CLEAN OPENING"
  and changes the candidate-agent certification wording accordingly.
- Existing opening rows created by older versions are backfilled using only
  central vote records whose timestamps precede the recorded opening time.
- Pre-existing votes are preserved and disclosed; they are never erased merely
  to manufacture a clean-zero report.

The opening_precast_voters column is added automatically to the local stream
database. No manual database migration is required.
