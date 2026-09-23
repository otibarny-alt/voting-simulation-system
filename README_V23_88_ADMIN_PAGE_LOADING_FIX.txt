V23.88 — ADMIN DATA FILES PAGE LOADING FIX

The Admin Data Files page no longer attempts schema creation while rendering.
Schema migration remains available through the explicit Run Schema Migration
button.

Master-register PostgreSQL connections now have bounded connection, statement
and lock waits. If the dedicated database is sleeping, recovering or
temporarily unavailable, the administrator page loads with a warning instead
of remaining stuck.
