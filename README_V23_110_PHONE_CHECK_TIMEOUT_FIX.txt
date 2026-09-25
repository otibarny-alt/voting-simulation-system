V23.110 — MEMBERSHIP PHONE CHECK TIMEOUT FIX

Membership updates no longer normalize every master-register phone row during
each duplicate check. That full-table calculation caused Render/PostgreSQL to
cancel the request at the statement-timeout limit.

The duplicate check now uses an indexed phone lookup against the accepted
Kenyan forms (07XXXXXXXX, 7XXXXXXXX, 2547XXXXXXXX and +2547XXXXXXXX). Duplicate
protection remains active for approved records, pending requests, new member
registrations, membership edits and administrator approvals.
