V23.209 — No-cache ECC ballot preview banner

1. The ballot preview loads the supplied ECC banner through a dedicated application route.
2. The route disables browser, proxy and Render cache reuse with no-store/no-cache headers.
3. The URL is release-versioned as v23_209_ecc.
4. The emergency-ballot PDF reads the exact same verified image file.
5. The deployment ZIP is flat: app.py, templates and static are at its root so extraction directly replaces the live project files.
