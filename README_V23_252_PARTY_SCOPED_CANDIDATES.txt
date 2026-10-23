2027 VOTING SIMULATION SYSTEM V23.252

PARTY-SCOPED CANDIDATE BALLOTS

- Every candidate-catalog request now includes the active party code.
- ODM branding requests only ODM candidates.
- UDA branding requests only UDA candidates.
- Candidate caches are separated by party so changing branding cannot reuse
  the previous party's cached ballot.
- A mismatched API response is rejected instead of showing another party's
  candidates.
- Includes all V23.251 voter-register and compatibility fixes.
