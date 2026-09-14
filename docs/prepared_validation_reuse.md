# Request-local canonical validation reuse

The prepared rigid-pose CPU consumer now shares successful canonical validation
reports within one invocation. The original Engine V2 validator still creates
each report. A cache hit requires the exact live object and runs the unchanged
full `AllAtomSystem.assert_integrity` check before using that report. This avoids
repeating structural validation and canonical serialization of unchanged sources.

The cache is bounded to 64 strong object references, belongs to the current
thread and request, and is discarded on normal return or exception. Nested
requests start independent scopes. There is no persistent cache, tensor-version
shortcut, frozen-source modification or replacement integrity implementation.
NumPy aliases, `.data`, and tensors in nested metadata remain fully checked.
Failures are never cached, and warning policy is applied on every use.

This reuses only canonical structural-validation reports. Original parameter
coverage, charge matching, source-file checks, geometry observations, minimum
distances, pocket admission, numerical evaluations and pre/post-calculation
integrity guards still execute. Every supplied pose is freshly evaluated or
retained as a failure. New objects, even with equal content, are revalidated.
Calls outside a rigid-request scope retain the original validator behavior.

No physical-validity, training-eligibility or scientific claim is added. Input,
score, checkpoint and output schemas are unchanged. The existing journal binds
all transitive product sources, including the helper; an older journal must use
its original source/environment. New code starts a new run rather than resealing
an old journal. Synthetic controls and source-bound actual measurements are
reported separately; a reduced validator call count is not a measured speedup.
