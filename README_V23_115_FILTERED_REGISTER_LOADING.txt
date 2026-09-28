V23.115 FILTERED VOTERS REGISTER LOADING

- The Voters Register page now opens immediately without loading the entire national register.
- Enter a National ID or select a county, then click Apply Filters to load records.
- National ID searches use the direct master-register lookup, including newly approved member 10703477.
- National ID equality preserves use of the master-register primary-key index.
- Location searches continue to combine the master register with the earlier Kobo membership CSV.
- This prevents the PostgreSQL statement timeout caused by an unfiltered national query.
- Serial numbers remain hidden from the on-screen voters-register view.
