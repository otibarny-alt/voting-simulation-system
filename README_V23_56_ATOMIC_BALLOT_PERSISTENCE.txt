V23.56 — ATOMIC BALLOT AND ALREADY-VOTED PERSISTENCE

Problem corrected
-----------------
Earlier builds saved six ballot choices locally, marked the voter as having
voted in PostgreSQL, and only then attempted an asynchronous tally mirror. A
mirror failure or Render restart could therefore leave an ALREADY VOTED marker
without the corresponding candidate selections in final tallies.

New rule
--------
All six anonymous category selections and the identifiable already-voted marker
are now committed in one PostgreSQL transaction. Either all seven records are
confirmed together or the transaction is rolled back and the Review page asks
the officer to retry. The completion screen is never shown after a partial save.

Recovery of earlier records
---------------------------
An old already-voted marker contains no candidate choices and cannot by itself
reconstruct a ballot. If the closed-stream tally page still displays the votes,
open it after deployment and use Retry Failed Reports so V23.55 stores the
structured certified tallies. If neither the tally page nor the durable result
events contain those choices, an administrator must verify the audit evidence
before permitting a supervised re-vote; the system must not invent selections.
