V23.149 - Permanent Background Phone Backfill

- Replaces row-by-row PostgreSQL updates with one permanent set-based SQL update.
- Stores generated values directly in master_voters.phone for later candidate-registration lookup.
- Runs PostgreSQL and Kobo CSV synchronization in a background worker so the browser request returns immediately.
- Displays running, completed, and error status on Admin Data Files.
- Preserves all existing phone values and skips conflicts or invalid National IDs.
- The update is idempotent and can be safely rerun.
