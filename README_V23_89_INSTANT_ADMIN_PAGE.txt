V23.89 — INSTANT ADMIN DATA FILES PAGE

The Admin Data Files GET request no longer contacts Kobo. Previously, listing
Kobo media could traverse multiple API pages and keep the only Render web
worker occupied until the proxy returned HTTP 502.

Kobo remains authoritative and is contacted only for explicit actions:

- Download Current membership_registration.csv
- Upload/replace membership_registration.csv
- Import Current Kobo CSV into PostgreSQL

The PostgreSQL status check also has tighter bounded waits. A temporarily
unavailable master database cannot prevent the rest of the page from loading.
