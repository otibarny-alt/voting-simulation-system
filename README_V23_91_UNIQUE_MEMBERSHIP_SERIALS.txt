V23.91 — AUTOMATIC UNIQUE MEMBERSHIP SERIAL NUMBERS

Every new membership application now receives a cryptographically random
12-digit serial number at submission. The applicant cannot enter or alter it.

Before allocation, the system checks the active PostgreSQL master register,
valid staged import rows, the current Kobo membership CSV, and every earlier
membership request. A PostgreSQL advisory transaction lock and unique index
also prevent simultaneous applications from receiving the same serial.

The serial is shown on the submitted application and is written to the
serial_no column when an administrator approves the application. Existing
membership edits retain their original serial number.

Optional setting:
  MEMBERSHIP_SERIAL_DIGITS=12

The supported range is 8 to 18 digits; 12 is the default.
