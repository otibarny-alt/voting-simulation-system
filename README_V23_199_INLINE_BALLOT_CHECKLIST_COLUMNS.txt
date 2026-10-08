V23.199 - INLINE BALLOT CHECKLIST COLUMNS

1. Removed the separate County Ballot Availability Checklist panel.
2. Added six checklist columns immediately after Registered Voters in the main
   filtered voter-totals table: President, Governor, Senator, Woman
   Representative, MNA and MCA.
3. Each displayed totals row now receives its own green check or red cross.
4. The checks follow the correct electoral scope:
   - President: national.
   - Governor, Senator and Woman Representative: county.
   - MNA: constituency.
   - MCA: ward.
5. Hovering a status shows its approved-candidate count.
6. The wide table scrolls horizontally on smaller screens.
7. One candidate-catalogue request supplies all displayed rows, preserving
   page performance.
8. No database migration is required.
