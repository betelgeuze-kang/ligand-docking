# Rust CPU provider

`rust_cpu` is a native, deterministic scalar execution backend. The kernel is
implemented in `rust/cpu-kernel` and linked behind the private versioned
provider ABI in `provider.h`; public callers continue to use the same opaque C
ABI as the C++ reference lane.

The provider is not an alias for `cpp_cpu_reference`. Both implementations run
the same synthetic fixtures independently, are bit-stable on repeated runs,
and must remain within the frozen cross-backend energy/force tolerance. This
backend is the host parity authority for the future `hip_safe` implementation,
but does not itself grant molecular execution or product-claim authority.
