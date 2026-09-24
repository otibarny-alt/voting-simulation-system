V23.101 — STREAM FINALISATION STATUS GATE

Adds a protected server-to-server endpoint that reports whether a polling-
station stream has been closed/finalised and how many category reports have
been archived. The entrance verifier uses it to stop further voter verification
after closure.

The endpoint requires the shared AGENT_SSO_SECRET and is not a public status
lookup. This package includes all V23.100 report-email and earlier fixes.

Deploy this package before Verifier V14.15.
