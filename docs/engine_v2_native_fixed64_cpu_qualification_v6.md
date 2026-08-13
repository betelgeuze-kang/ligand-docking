# Engine V2 native fixed64 CPU qualification v6 archive

Profile v6 is a frozen, unconsumed predecessor record. It was reviewed at
`0c4d0b911fbc6e75b1e806620d36a282fc24893a`, merged as main commit
`12b220e096665ec5664e729d3d60baf577578c56`, and then superseded by v7 lane
metrics without creating a reservation or running the v6 exactly-once
measurement.

The immutable identities are:

- profile: `engine_v2_native_fixed64_cpu_synthetic_v6`
- profile SHA-256: `fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928`
- 193-source manifest SHA-256: `988108202cceafff669930f804a8bc292ec2a364dd8c016bd9d4b7ecdb190f45`
- archive SHA-256: `efb3efd0d863fb6797e9651bf7ba5ef63ab7eb09d5bcc3eef947b7fcd4709551`
- required checks at reviewed head: 33 successful
- unresolved review threads: 0

The canonical archive is
`config/engine_v2_native_fixed64_cpu_profile_v6_archive.json`; its packaged
mirror is
`rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json`.
The original profile and source manifest remain in the repository only as
historical inputs needed to verify the archive and v7 predecessor binding.

The archive verifier requires canonical JSON, byte-identical packaged archive,
the exact profile/source identities, `execution_consumed=false`,
`reservation_created=false`, and every authority bit false:

```bash
python3 tools/verify_engine_v2_native_fixed64_cpu_profile_v6.py
```

Profile v6 must not be built or executed as a new qualification. Its historical
evidence verifier remains available only to validate already-existing v6-format
files; it cannot create evidence or grant authority. GitHub Actions checks the
archive and the verifier interface but never sets the v6 qualification-build
opt-in or invokes `--run-output`.

The archive grants no qualification, scientific, product-performance, public
benchmark, Stage 0, Fresh-128, reservation, molecular, or HIP authority.
