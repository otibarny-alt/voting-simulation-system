V23.181 STALE TERMINAL LOCK RECOVERY

Fixes voting terminals that remain stuck on the stream-opening page after an
administrator resets/reopens a stream or clears test election data.

The voting terminal now treats a missing central lock row or an already
released central lock row as successfully released. This safely clears the
browser's signed pending-release marker and permits the terminal to reopen the
assigned stream. A central lock that still exists and is active continues to
block takeover by another device.

Deployment:
1. Deploy this package to the Voting service only.
2. Refresh the stuck voting-terminal browser.
3. Capture the opening snapshot and open the stream.

No database migration is required.
