V23.138 - Single Active Serial Lookup Terminal

- A serial_lookup_id can be active on only one device at a time.
- A second terminal using the same ID is blocked with a clear message.
- The active browser renews its exclusive lease every 30 seconds.
- Logging out releases the ID immediately.
- If a device closes or loses connectivity without logging out, the lease expires
  after 120 seconds so the ID can be used again.
- Verification and Voting terminal sessions are not changed.

DATABASE_URL must be configured on the Voting System Render service so all
instances share the same exclusive lookup-terminal lease.
