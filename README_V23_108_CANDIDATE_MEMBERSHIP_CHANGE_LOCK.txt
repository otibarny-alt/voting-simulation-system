V23.108 - CANDIDATE MEMBERSHIP CHANGE LOCK

Members whose National ID has any record in Candidate Registration may view
their membership details but cannot unlock, edit, submit, or obtain approval
for membership corrections.

The restriction is enforced at three levels:
1. The Unlock button is hidden and the member page remains read-only.
2. Manipulated membership POST requests are rejected server-side.
3. Administrator approval rechecks candidate registration before applying a
   pending membership request.

The check fails closed: if Candidate Registration cannot be verified, editing
and approval remain temporarily locked.

Authentication uses CANDIDATE_ELIGIBILITY_TOKEN. If that variable is omitted,
the existing shared SYSTEM_RESET_TOKEN is used for backward-compatible setup.
