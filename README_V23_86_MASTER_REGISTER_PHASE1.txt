V23.86 — PostgreSQL Master Voters Register, Rollout Phase 1

PURPOSE
The live system no longer needs to load a complete membership CSV when a
dedicated PostgreSQL register is configured. Serial-number searches, National
ID membership lookups, registered-voter totals, dashboard geography totals and
polling-station totals use indexed SQL queries.

REQUIRED NEW RENDER ENVIRONMENT VARIABLE
MASTER_REGISTER_DATABASE_URL=<internal connection string of the dedicated
Render PostgreSQL master-register database>

Set the identical value on:
1. Voting Simulation System
2. Voter Verification System

Keep DATABASE_URL unchanged. It continues to store voting locks, status,
reports and other operational data. The master register is deliberately
isolated from those workloads.

SAFE INITIAL IMPORT
Use a Render one-off job or shell with this application build and the new
environment variable configured. Do not upload a 10-million-row file through
the normal browser request.

1. Stage and validate without changing the live register:
   python import_master_register.py stage /path/membership_registration.csv --mode replace

   If the process is interrupted after a committed 100,000-row chunk, resume
   the same batch using its UUID:
   python import_master_register.py stage /path/membership_registration.csv --resume-batch BATCH_UUID

2. Copy the printed batch UUID and review it:
   python import_master_register.py status

3. Export rejected rows, if any:
   python import_master_register.py errors BATCH_UUID rejected_rows.csv

4. After reconciling totals, promote the valid staged rows atomically:
   python import_master_register.py promote BATCH_UUID

   Promotion is blocked when rejected rows exist. Correct and restage them.
   Only after explicit review, an administrator may promote valid rows while
   excluding rejected rows with: --allow-rejections

Use --mode merge for a later incremental file. Replace mode deactivates voters
that are absent from the promoted full register; merge mode leaves them active.

CSV FIELD ALIASES
The importer accepts the existing headings including national_id_no,
serial_no, odm_membership_no, first_name, middle_name, surname, phone_no,
dob, county, constituency, ward, poll_station, poll_station_code,
member_id_photo and member_passport_photo.

ROLLOUT SAFETY
- CSV and Kobo fallbacks remain available temporarily.
- The master register is preferred whenever MASTER_REGISTER_DATABASE_URL exists.
- Do not delete the old CSV until national, county, constituency, ward and
  polling-station totals have been reconciled.
- Both services support MASTER_REGISTER_STRICT=true after reconciliation. This
  disables large-CSV lookup fallbacks and prevents web-worker memory spikes.

PHOTOS
id_photo_ref and passport_photo_ref are preserved. Before final cutover, photo
references must be confirmed as durable URLs or migrated to object storage;
the relational database should not contain the image bytes.
