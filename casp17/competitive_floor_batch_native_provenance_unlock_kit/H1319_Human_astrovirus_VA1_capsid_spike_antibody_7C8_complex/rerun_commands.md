# CASP17 Batch Native/Provenance Unlock Rerun Commands



```bash
python3 tools/build_casp17_competitive_floor_target_identity_clearance_operator_intake.py
```

```bash
python3 tools/sync_casp17_competitive_floor_target_identity_clearance_manifest_stub.py
```

```bash
python3 tools/build_casp17_competitive_floor_target_identity_clearance_workorder_audit.py
```

```bash
python3 tools/build_casp17_competitive_floor_target_identity_metric_runway.py
```

```bash
python3 tools/build_casp17_competitive_floor_native_provenance_operator_packet.py
```

```bash
python3 tools/build_casp17_competitive_floor_native_provenance_operator_packet_completion_audit.py
```

```bash
python3 tools/build_casp17_competitive_floor_native_provenance_metric_unlock_bridge.py
```

```bash
python3 tools/build_casp17_competitive_floor_first_native_provenance_unlock_kit.py
```

```bash
python3 tools/build_casp17_competitive_floor_batch_native_provenance_unlock_kit.py
```

```bash
python3 tools/build_casp17_workbench_index.py
```



CASP17 competitive-floor batch native/provenance unlock operator kit only. It collects all blocked native/provenance target packets into one operator-fill workspace with per-target folders, a batch intake CSV, action matrix, and rerun commands. It does not fetch native structures, copy coordinates, fill or trust provenance, clear no-leak evidence, compute native accuracy, serialize a CASP author code, or submit to CASP.
