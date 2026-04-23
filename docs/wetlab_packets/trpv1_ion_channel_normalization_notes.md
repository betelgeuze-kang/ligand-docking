# TRPV1 Ion Channel Shortlist Normalization Notes

## Current Status

The top `TRPV1_ION_CHANNEL_BLIND` shortlist is now identity-normalized. Each candidate in `docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv` includes:

- `CHEMBL` identifier
- `InChIKey`
- PubChem title / IUPAC-style normalized name
- local ranking score and reference affinity

## What Is Ready

- compound identity is now explicit enough for partner review
- shortlist ranking is preserved from the in-repo TRPV1 blind run
- candidates can now be handed to a CRO or vendor contact for sourcing feasibility review

## What Is Still Missing

- vendor catalog match
- purchase availability
- salt/form confirmation
- shipment and assay solubility confirmation

## Recommended Next Step

Use the top 3 to 5 rows of `docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv` as a sourcing request packet, not yet as a final assay-ready control list.

## Source Systems Used

- ChEMBL molecule API
- PubChem PUG REST property endpoint
