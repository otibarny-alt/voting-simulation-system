V23.114 — FAST VOTERS REGISTER AND NATIONAL ID SEARCH

The Admin Voters Register now has a National ID filter. Searching for an ID,
including newly approved member 10703477, queries the indexed master_voters
National ID key directly and displays the matching record without being hidden
behind the 5,000-row preview limit.

When the PostgreSQL master register is active, the view now combines it with
the cached membership_registration.csv legacy snapshot and does not download
and paginate every live Kobo submission during each page load. This removes the
largest source of register-loading delays while retaining pre-migration members.
