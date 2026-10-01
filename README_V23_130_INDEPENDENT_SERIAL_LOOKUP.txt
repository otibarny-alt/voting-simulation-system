V23.130 Independent ID to Serial Number Lookup
===============================================

This release separates the ID lookup from Admin Data Files.

Standalone address
------------------
/id-serial-lookup

Behavior
--------
1. The lookup address can be opened independently without signing into Admin
   Data Files.
2. It contains no link or navigation into Admin Data Files.
3. Admin Data Files remains protected by its existing administrator login.
4. Admin Data Files includes a link that opens the independent lookup in a new
   browser tab.
5. A successful lookup displays:
   - membership serial number;
   - voter's name; and
   - polling station.
6. Lookup responses use no-cache and no-index headers.
7. The standalone form uses a CSRF token that is separate from the Admin Data
   Files security token.

The previous /admin/data-files/id-serial-lookup bookmark redirects to the new
standalone address.
