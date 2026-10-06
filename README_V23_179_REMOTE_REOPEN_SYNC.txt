V23.179 REMOTE ADMIN REOPEN SYNCHRONISATION

Deploy together with Verification V14.35.

- Admin reopening no longer transfers stream ownership to the administrator's browser.
- The originally paired remote voting terminal detects reopening automatically.
- Streams already reopened by an older build automatically restore ownership to the original signed remote terminal.
- The remote terminal restores its active-stream cookie and reloads without re-pairing.
- Existing electronic votes remain preserved and new eligible votes are added.
- Stale closing PDFs and the earlier paper tally are unlocked/removed on reopen.
- Closing again regenerates reports and combined tallies from preserved plus new votes.

No manual schema migration is required.
