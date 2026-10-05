V23.168 — HYBRID PAPER / ELECTRONIC VOTING

- The voting terminal admits only voters who selected Electronic Voting during
  entrance verification and have a current, unused approval for the same station.
- A voter who selected Paper Voting is already marked Voted and is explicitly
  blocked from the electronic ballot.
- A successful electronic ballot is recorded as ELECTRONIC_BALLOT.
- The voters register displays Voted / Not Voted and the voting method: Paper or
  Electronic. Both methods are included in the Voted count.
- Test-data reset clears the shared voter_status records, returning both paper
  and electronic voters to Not Voted while preserving candidates.

DEPLOYMENT REQUIREMENT
Deploy this package before Verification System V14.28. Both services must use
the same PostgreSQL database and the same ELECTION_ID. No schema migration is
required.
