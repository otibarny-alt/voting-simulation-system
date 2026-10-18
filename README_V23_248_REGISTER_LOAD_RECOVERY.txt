2027 VOTING SIMULATION SYSTEM V23.248

VOTERS REGISTER LOAD RECOVERY

1. The filtered voter rows now render before the slower full-filter voting
   summary is calculated.
2. Exact polling-station, voted and not-voted totals refresh immediately in
   the background and then continue refreshing every 60 seconds.
3. A register query failure is displayed inside the protected register page
   instead of returning HTTP 502 and being replaced by the terminal
   "reconnecting" screen.
4. The V23.247 per-record Edit and Delete buttons remain available in the last
   column.

Deploy this package as the voting system service and redeploy normally.
