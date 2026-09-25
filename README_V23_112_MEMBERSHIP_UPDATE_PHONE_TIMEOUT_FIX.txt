V23.112 — MEMBERSHIP UPDATE PHONE TIMEOUT FIX

The approved-member phone-duplication query now has its own bounded 30-second
database window instead of inheriting the four-second public lookup timeout.

Membership submission also performs the authoritative phone check only once.
The check remains serialized with a PostgreSQL advisory transaction lock until
the pending request is committed, so simultaneous registrations cannot claim
the same phone number.

National ID verification retains its short timeout. Candidate membership locks,
field-edit restrictions and administrator approval rechecks remain unchanged.
