V23.57 — MEMBERSHIP APPROVAL DATABASE CONNECTION FIX

The public membership page previously called the global database initializer,
which also prepared voting, report repository, dashboard and voter-access
tables. A slow unrelated table could therefore display:
"corrections cannot be submitted until the Render approval database reconnects."

V23.57 initializes only membership_change_requests and its two small indexes
for these operations:
- checking the latest member request;
- submitting a new registration or correction;
- administrator approval;
- administrator rejection;
- administrator request listing.

All V23.56 atomic-ballot and V23.55 certified-consolidation fixes are retained.
