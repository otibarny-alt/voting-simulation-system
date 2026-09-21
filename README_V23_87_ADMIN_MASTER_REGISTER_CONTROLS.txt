V23.87 — ADMIN MASTER REGISTER CONTROLS

The protected Admin Data Files page now provides:

1. Run Schema Migration
   Creates or upgrades the dedicated PostgreSQL master-register tables and
   indexes. The operation is idempotent and does not delete existing voters.

2. Import Current Kobo CSV
   Downloads membership_registration.csv from the configured Kobo project and
   stages it in PostgreSQL using a background worker. The browser returns
   immediately, avoiding Render HTTP request timeouts for large files.

3. Durable batch status
   Recent staging, validation, rejection and promotion counts are displayed
   from voter_register_import_batches.

4. Activate Register
   A STAGED batch can be promoted only when it contains valid voters and has no
   rejected rows. Replacement activation is explicit and protected by the
   existing administrator login and CSRF token.

Required Render environment variable:
  MASTER_REGISTER_DATABASE_URL=<dedicated PostgreSQL Internal Database URL>

Keep the service's existing DATABASE_URL unchanged. Keep
MASTER_REGISTER_STRICT=false until the imported totals and sample lookups have
been reconciled.
