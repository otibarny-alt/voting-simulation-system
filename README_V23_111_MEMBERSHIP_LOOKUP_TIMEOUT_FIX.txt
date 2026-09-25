V23.111 — MEMBERSHIP LOOKUP TIMEOUT FIX

The application no longer attempts to create a phone index during the first
public membership lookup. On Render, that runtime schema operation could exceed
the PostgreSQL statement timeout and make National ID verification unavailable.

Phone duplication prevention continues to use direct comparisons against the
accepted Kenyan phone formats. No database migration or index creation is
required during a public registration, edit, lookup or approval request.
