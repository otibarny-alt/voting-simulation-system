V23.178 PAPER VOTE CEILING

Deploy this Voting package together with Verification V14.34.

- Reads the distinct voters recorded for Paper Voting in the exact polling station and stream.
- Displays that number as the maximum for every candidate category.
- Blocks a category whose candidate totals exceed the paper-voter count.
- Allows a lower category total because a voter may skip a contest.
- Rechecks the rule on the server before saving; browser-side checks cannot bypass it.
- Recovers the correct stream for earlier paper records from the approving entrance-terminal ID.

No manual schema migration is required.
