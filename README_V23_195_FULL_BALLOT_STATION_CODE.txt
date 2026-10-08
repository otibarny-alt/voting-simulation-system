V23.195 - FULL POLLING-STATION CODE IN BALLOT REFERENCES

1. Ballot references now print the complete polling-station code instead of
   spreadsheet scientific notation.
2. Scientific values such as 1.23456789012345E+15 are expanded to their full
   digit representation before display.
3. Digit-only station codes are preserved exactly, including leading zeroes.
4. The correction applies to both the filtered web preview and PDF ballots.
5. Candidate layout, cropped banner, watermarks and dynamic page height remain
   unchanged.
6. No database migration is required.
