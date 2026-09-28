V23.117 NORMALIZED WARD AND POLLING-STATION FILTERS

- Ward and polling-station selections are now matched after values have been
  canonicalized against county_main.csv.
- PostgreSQL still narrows the query by National ID, county and constituency,
  keeping register loading fast.
- Harmless differences between stored labels and hierarchy keys/spacing no
  longer exclude valid voters.
- Voter 10703477 is retained when filtering through NORTH SEME and RATTA
  PRIMARY SCHOOL, and is included in the broader SEME result set.
- Register statistics now count the master-register records remaining after
  normalized filtering rather than running a second strict COUNT query.
