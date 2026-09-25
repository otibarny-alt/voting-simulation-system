V23.107 - MEMBERSHIP VIEW/EDIT FIELD LOCKS

Changes
-------
1. Membership serial number is no longer displayed on the member details/edit page.
2. National ID remains permanently read-only.
3. ODM registration number remains permanently read-only.
4. First name, middle name, and surname remain permanently read-only for existing members.
5. Unlocking an existing record enables only:
   - Phone number
   - County, constituency, ward, polling station, and polling station code
   - ID photo and passport photo
6. Server-side validation ignores attempted changes to locked identity fields and preserves their authoritative saved values.

New membership applications still collect applicant names, while the National ID and generated ODM registration number remain protected.
