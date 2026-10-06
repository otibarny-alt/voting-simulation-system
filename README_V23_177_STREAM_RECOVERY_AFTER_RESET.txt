V23.177 STREAM RECOVERY AFTER TERMINAL RESET

Fixes a post-reset/deployment state where the browser and PostgreSQL still held
the valid station/stream lock but Render's ephemeral SQLite stream row was
missing. The page displayed blank Polling Station and Stream fields and the
Go to Close Voting Stream link had no destination.

- Reconstructs the local stream session from the authoritative PostgreSQL lock.
- Restores polling station, stream, opening state and Close Voting Stream.
- Preserves all central electronic votes.
- Shows a safe Refresh and Restore Stream panel if PostgreSQL is temporarily
  unavailable instead of displaying blank fields or a dead fragment link.

Verification V14.33 remains unchanged. No schema migration is required.
