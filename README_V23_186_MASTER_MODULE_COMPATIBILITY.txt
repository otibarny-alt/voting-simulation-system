V23.186 VOTER TOTALS MASTER-MODULE COMPATIBILITY

Fixes:
  Voter totals PDF could not be generated: module 'master_register' has no
  attribute 'voters_register_grouped_totals'

The PDF now prefers the optimized grouped-count query when it is available. If
Render is still loading an older master_register.py module, it safely falls
back to the existing voters-register summary-row API and performs the same
geographic aggregation without changing or guessing voter totals.

No database migration is required.
