V23.182 PAPER TALLY REPORT GATE

Fixes final reports that could be generated without paper vote entries even
though voters in the stream selected Paper Voting.

Rules enforced:
- If no voter selected Paper Voting, a zero paper tally remains valid.
- If one or more voters selected Paper Voting, the complete paper submission
  cannot be all zero.
- Individual candidate categories may remain zero when paper voters skipped
  that category.
- Each category total must remain at or below the authoritative number of
  paper voters for the station and stream.
- Final tally display and PDF repository deposit independently enforce the
  paper-tally gate.
- Invalid all-zero submissions saved by older builds can be corrected. Any
  earlier electronic-only PDF/certification is removed and regenerated from
  the corrected combined electronic-plus-paper results.

No database migration is required.
