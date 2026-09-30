V23.128 ID to Serial Number Lookup
==================================

This release adds a protected ID-to-serial-number lookup to Admin Data Files.

Admin workflow
--------------
1. Sign in to Admin Data Files.
2. Select "Open ID to Serial Number Lookup".
3. Enter a valid 7- or 8-digit National ID.
4. The page displays only the related membership serial number.

Data and privacy rules
----------------------
- The PostgreSQL master register is checked first.
- Existing Kobo membership sources are used as fallback according to the
  application's current register configuration.
- No name, phone, ODM number, location, photo, or other member data is shown.
- The page is protected by the existing repository administrator login and a
  CSRF token.
