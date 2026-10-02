V23.151 - Lock Wait and Accurate Failure Progress

- Disables PostgreSQL lock timeout only for the background permanent-phone maintenance job.
- Allows an active database transaction to finish instead of reporting a false lock-timeout failure.
- Stops Kobo synchronization when the permanent PostgreSQL update fails.
- Displays PostgreSQL failures at 15% and Kobo failures at 65%, instead of incorrectly showing 100% failed.
- Updates the status banner and retry button live without reloading the page.
