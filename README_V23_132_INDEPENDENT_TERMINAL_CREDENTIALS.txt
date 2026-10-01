V23.132 Independent Terminal Credentials Lookup
================================================

Standalone address
------------------
/terminal-credentials-lookup

Behavior
--------
1. The page is independent of Admin Data Files and contains no administration
   links.
2. Credentials remain hidden until County, Constituency, Ward and Polling
   Station have all been selected.
3. Results are limited to the selected polling station and display each stream's:
   - Entrance Verification Terminal ID;
   - Entrance Verification Terminal password;
   - Voting Terminal ID; and
   - Voting Terminal password.
4. The filtered credentials can be printed.
5. Admin Data Files contains a link that opens this independent page in a new
   browser tab.
6. Responses are marked no-cache and no-index.
