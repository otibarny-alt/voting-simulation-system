CERTIFIED RESULTS FEED FIX

Deploy this package to the main voting-system Render service.

The results APIs now read the latest formally submitted results from
simulation_certified_stream_tallies first. These records contain the merged
electronic and paper tally written when the closing report is deposited.

Previously the dashboard API read only raw electronic and paper event tables,
so a valid submitted result such as Lokornoi Primary School could exist in
PostgreSQL while the public dashboards displayed no stream, candidates or
votes.

Certified streams remain CLOSED and visible after terminal release or reset.
If no certified result exists for a category, the existing raw-event fallback
continues to operate.
