V23.135 Clean Reset Preserves Candidates
=========================================

The Clean Testing Reset no longer calls the Candidate Registration service and
does not delete candidate applications, approvals or ballot catalogues.

The reset still clears:

- local and central vote records;
- voter voting-status records;
- entrance approvals;
- stream locks and sessions;
- certified tallies; and
- opening and closing reports.

Because voter_status and local vote records are cleared, the dynamic voters
register shows every member as Not Voted after the reset.

The reset screen, confirmation prompt, success message and failure message have
been updated to describe the preserved candidates accurately.

SYSTEM_RESET_TOKEN is no longer required for this local/central voting reset,
because the Candidate Registration service is no longer contacted. Protected
administrator login, CSRF validation and the typed confirmation remain active.
