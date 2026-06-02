# CASP17 Current Escrow External Timestamp Packet Rerun Commands

- `python3 tools/build_casp17_current_prospective_strict_blind_escrow.py`
- `python3 tools/build_casp17_current_escrow_external_timestamp_packet.py`
- `python3 tools/build_casp17_workbench_index.py`

CASP17 current escrow external timestamp packet only. It converts the prospective strict-blind escrow into a commit/push-ready timestamp manifest with candidate paths, SHA256 hashes, review links, and native-pending state. It does not commit, push, submit to CASP, copy coordinates, serialize a CASP author code, compute native accuracy, or mark strict-blind competitive proof.
