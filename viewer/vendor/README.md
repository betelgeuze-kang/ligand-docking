# Viewer Vendor Assets

The viewer loads browser runtime dependencies from this directory for
self-hosted and offline delivery. `manifest.json` records pinned upstream URLs,
versions, sizes, SHA-256 hashes, and license provenance. `THIRD_PARTY_NOTICES.md`
summarizes the vendored packages for operator release review.

Runtime HTML must not load CDN or Google Fonts URLs. Refresh assets only through
an operator-reviewed update that also updates `manifest.json`,
`THIRD_PARTY_NOTICES.md`, and the viewer self-hosted asset tests.
