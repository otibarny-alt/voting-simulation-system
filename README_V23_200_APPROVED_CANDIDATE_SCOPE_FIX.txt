V23.200 - APPROVED CANDIDATE BALLOT-SCOPE FIX

1. Corrected the inline ballot checklist to read approved candidate submissions
   with the geographic scope required by the candidate API.
2. President candidates are loaded nationally and apply to every county.
3. A county-scoped approved-candidate catalogue is loaded once for each county
   represented in the table. This correctly identifies Governor, Senator and
   Woman Representative ballots in that county.
4. MNA availability is narrowed to the constituency in each row.
5. MCA availability is narrowed to the constituency and ward in each row.
6. The verified West Pokot example now reports county ballots, Kapenguria MNA
   ballots and the Mnagei MCA ballot correctly.
7. No database migration is required.
