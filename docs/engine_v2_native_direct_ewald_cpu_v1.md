# Engine V2 native direct-Ewald CPU ABI v1

Issue #434 step 2 places the independently frozen direct-Ewald semantics from
PR #435 behind a separately versioned native development boundary. It does not
change the frozen Engine ABI 1.21 force-field descriptor or repurpose any of
its reserved fields.

The public C header is `include/betelgeuze/direct_ewald.h`. Its ABI identity is
1.0.0 (`BG_DIRECT_EWALD_ABI_VERSION=1`) and its ELF export node is
`BETELGEUZE_DIRECT_EWALD_1.0`. Mach-O uses an exact positive export allowlist
containing the current 151 public C symbols. This final-link boundary prevents the
private Rust provider archive, including both direct-Ewald provider entry
points, from entering the dylib ABI. A hosted macOS build checks the complete
defined-external symbol set with `nm`; Linux retains exact symbol-version checks.
The API owns an opaque immutable model, energy, force, and typed-error
descriptors. Model creation deep-copies the settings,
exclusions, and scaled-pair rows. Failed creation returns a null handle; failed
evaluation leaves the caller-owned energy, force channels, force count, and
other output state uncommitted. Descriptor initializers are transactional on
ABI mismatch. A valid error descriptor is cleared at call entry, so an untyped
ABI or capacity failure cannot leak a typed code/detail from an earlier call.
The same clearing rule applies before mandatory context/system/model/energy or
parameter null-input rejection. Create validates the writable model and error
storage against the parameter descriptor and every plausibly usable pair-rule
channel span before any write, so a raw FFI alias cannot corrupt an input.

Two explicit host lanes implement the same frozen semantics. The Rust CPU lane
uses the pinned `libm` implementation and reproduces all five parent energy
components and twelve parent force components bit-for-bit on the frozen
four-charge fixture. The independent C++ CPU reference lane uses its platform
strict standard-math implementation, repeats identical inputs bit-for-bit
within that lane, and is compared to Rust with the frozen
`5e-12 * max(1, abs(reference))` component tolerance. The test also requires
matching typed ambiguity, damping-underflow, and phase-underflow categories.
Energy-only calls preserve the full-evaluation energy bits while omitting force
storage and real-space, reciprocal-space, and pair-correction force
accumulation in both CPU lanes.
No production native source links the standalone `rust/reference-ewald` crate.

The Rust system crate mirrors the C ABI, compiles C11 header and C++ layout
probes, and vendors byte-identical native sources. The safe runtime owner is
neither `Send` nor `Sync`, destroys its native model once, maps all frozen typed
error codes, guards a non-null handle even on an abnormal failing create
return, and rejects unsupported lanes before evaluation. These bindings expose
the CPU development boundary; they do not integrate a long-range term into
shared-runtime dynamics or checkpoints. That remains Issue #434 step 3.
The runtime integration test reads its crate-local
`tests/fixtures/direct_ewald_v1.tsv`; the evidence verifier requires those
bytes to equal the parent reference fixture exactly.

HIP backends return the unsupported-backend status. They do not launch a
device operation and do not fall back to a CPU lane. This slice implements
direct Ewald, not PME.

## Immutable evidence

The profile is
`config/engine_v2_native_direct_ewald_cpu_profile_v1.json`; its source binding
is `config/engine_v2_native_direct_ewald_cpu_profile_v1_sources.json`. The
manifest uses canonical ASCII JSON and sorted unique rows containing repository
path, byte count, and SHA-256. It covers the direct implementation, ELF and
Mach-O public export policies, private ABI surface, direct tests and their
crate-local frozen fixture, Rust system/runtime binding files, vendor copies,
the primary Rust workspace, the separate `rust_engine_v2` native-wheel Cargo
manifest and lockfile, and the four parent-oracle inputs.
It also binds the verifier itself and its `tools` package initializer. Neither
contains the resulting profile hash, so this remains acyclic. It deliberately
excludes the profile, manifest, profile-hash unit test, documentation, and
workflow so that the profile can bind the raw manifest SHA-256 without a hash
cycle. It is a focused slice binding rather than a claim of a complete linker
or repository transitive closure.

The verifier is read-only by default:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_cpu_v1.py
```

When and only when an intentional source change is complete, regenerate the
sorted manifest and update the profile's manifest count/hash in one explicit
command:

```bash
python3 tools/verify_engine_v2_native_direct_ewald_cpu_v1.py --refresh
```

Adding or removing a discovered direct-Ewald ABI probe, vendor source, runtime
binding, or test causes normal verification to fail until that explicit
refresh. The unit test separately freezes the resulting raw profile SHA-256.

The parent reference binding is exact:

- PR #435 reviewed head `b94e4c008db1c8414f5d0f24fa266c85c828d13c`
- merge commit `ba008fcaa75891bca45e7b3d33b67449d80fb7d4`
- merge tree `0530a50af2cceeff02341ccb6fab141fd8c43726`
- profile SHA-256 `dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c`
- scalar source SHA-256 `2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e`
- frozen fixture SHA-256 `a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338`
- standalone lockfile SHA-256 `cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d`

## Claim boundary

This is deterministic tiny-fixture CPU development evidence. It grants no
PME, bulk-solvent, equilibration, NPT, production-MD, molecular-execution,
scientific, accuracy-at-scale, performance, acceleration, product,
reservation, Stage 0, Fresh-128, public-benchmark, or HIP-device authority.
The external reservation and historical-execution blockers and 32 unresolved
operational decisions remain controlling. The consumed native fixed64 CPU-v7
qualification is not invoked or rerun by this profile, verifier, test, or
workflow.
