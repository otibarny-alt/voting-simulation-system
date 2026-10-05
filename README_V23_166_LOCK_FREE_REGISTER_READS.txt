V23.166 - Lock-free voters-register reads

Fixes:
  Register could not be generated: canceling statement due to lock timeout

Cause
-----
Render recycles Gunicorn workers. Each new worker previously ran the complete
master-register CREATE TABLE, ALTER TABLE and CREATE INDEX schema routine from
the first ordinary voter lookup. Those DDL statements request stronger
PostgreSQL locks and could time out behind an import, membership update or
other active transaction.

Correction
----------
Normal register, membership, candidate-eligibility and dashboard reads now use
a lightweight PostgreSQL catalog probe. If the established master tables are
present, no DDL is executed and the read continues immediately.

Only the administrator's explicit Run Schema Migration control uses
force=True and performs CREATE/ALTER/INDEX work.

No database migration is required for this release. Deploy the package to the
main voting-simulation service and restart it once after deployment.
