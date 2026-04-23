# External Governance Note

The current package includes a simple governance seal layer over the accepted reviewer-facing artifacts. This seal is not presented as a third-party notarization system. Instead, it provides a frozen SHA256 manifest over the key artifacts that define the current accepted package and submission bundle.

The intent is to make post-freeze mutation easier to detect and reviewer-side verification easier to perform.

The current seal artifact is:

- `runs/biorxiv_external_validation_governance_seal_current.md`

The sealed file set includes the promoted package zip, reviewer index, current run summary, claim matrix, audit report, main validation table, temporal baseline, and submission-assets zip.
