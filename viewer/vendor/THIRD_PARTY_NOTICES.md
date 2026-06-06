# Viewer Third-Party Notices

This notice records the browser runtime dependencies vendored under
`viewer/vendor/` for self-hosted/offline delivery.

It is provenance for product release review, not legal advice and not final
commercial redistribution approval. The operator must confirm license
compatibility before a commercial bundle is shipped.

## Pinned Runtime Assets

| package | version | local asset(s) | declared license | upstream license source |
| --- | --- | --- | --- | --- |
| molstar | 4.5.0 | `viewer/vendor/molstar/4.5.0/molstar.css`, `viewer/vendor/molstar/4.5.0/molstar.js` | MIT | https://cdn.jsdelivr.net/npm/molstar@4.5.0/LICENSE |
| plotly.js-dist-min | 2.35.2 | `viewer/vendor/plotly/2.35.2/plotly-2.35.2.min.js` | MIT | https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/LICENSE |
| jszip | 3.10.1 | `viewer/vendor/jszip/3.10.1/jszip.min.js` | (MIT OR GPL-3.0-or-later) | https://cdn.jsdelivr.net/npm/jszip@3.10.1/LICENSE.markdown |

## Review Notes

- Asset hashes, sizes, source URLs, package names, and license source URLs are
  machine-recorded in `viewer/vendor/manifest.json`.
- JSZip is recorded with its declared dual-license expression. Commercial
  redistribution should explicitly document the chosen compatible license path.
- Refreshing any asset requires an operator-reviewed manifest and notice update.
