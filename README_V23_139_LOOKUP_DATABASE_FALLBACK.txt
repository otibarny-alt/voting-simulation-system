V23.139 - Serial Lookup Database Fallback

The exclusive Serial Lookup terminal lease now selects its PostgreSQL database
in this order:

1. SERIAL_LOOKUP_DATABASE_URL
2. MASTER_REGISTER_DATABASE_URL
3. DATABASE_URL

This prevents an obsolete or unresolvable general DATABASE_URL from blocking
lookup-terminal login when the master-register database is available. Raw
database hostnames are no longer exposed in the login error message.

For Render, no new variable is needed when MASTER_REGISTER_DATABASE_URL is
already valid. Otherwise set SERIAL_LOOKUP_DATABASE_URL to a working PostgreSQL
Internal Database URL available to the Voting System service.
