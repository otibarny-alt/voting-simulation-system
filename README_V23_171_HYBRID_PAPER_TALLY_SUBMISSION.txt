V23.171 — HYBRID PAPER TALLY SUBMISSION

Workflow
1. The voting stream is formally closed.
2. The assigned voting terminal is redirected to Paper Ballot Tally Submission.
3. The agent enters a non-negative whole-number paper total for every approved
   candidate in all six election categories. Zero must be entered where needed.
4. The page displays each candidate's electronic votes and a live combined preview.
5. Submission is validated against the current approved candidate ballot.
6. The paper tally is committed atomically and permanently locked for that stream.
7. Final tally pages, certified reports, winners reports and all six dashboard
   feeds aggregate electronic votes plus paper votes.

Audit and safety
- Electronic ballot events are never edited or replaced.
- Paper votes remain in separate PostgreSQL tables with submitter and timestamp.
- Duplicate submission is rejected using a central unique stream key.
- Candidate IDs and names are validated server-side.
- Negative, fractional and incomplete totals are rejected.
- Final tally access requires completion of the paper-tally form, including an
  all-zero submission when no paper ballots were issued.
- Paper-only streams can generate final tallies.
- Clean Test Data removes paper tally test records while preserving candidates.

The required PostgreSQL tables are created automatically. No manual migration
is required. Verification System V14.30 remains compatible.
