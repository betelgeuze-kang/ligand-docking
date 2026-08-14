# Engine V2 native CPU runtime artifacts v1

This contract makes the release-candidate workflow retain three ABI-specific artifacts for the native CPU package instead of retaining only the CPython 3.11 row:

| Python | ABI | Artifact-name ABI component | Required payload |
| --- | --- | --- | --- |
| 3.10 | `cp310-cp310` | `cp310-cp310` | reproducible wheel and SPDX SBOM |
| 3.11 | `cp311-cp311` | `cp311-cp311` | reproducible wheel and SPDX SBOM |
| 3.12 | `cp312-cp312` | `cp312-cp312` | reproducible wheel and SPDX SBOM |

Every matrix row builds the wheel twice through the frozen native build wrapper and requires byte identity before upload. The artifact name binds the package version, ABI, workflow run ID, and run attempt. Each artifact retains both the wheel and its SPDX document for 14 days. A missing file fails the upload.

These files are build inputs, not execution evidence. A later synthetic CPU performance profile may select only an ABI-matching artifact produced by a main push. That profile must independently freeze the repository, workflow path, run and attempt, head SHA, artifact ID, name, digest, size, expiration, wheel and SBOM checksum binding, native extension SHA-256, and runtime executable SHA-256. Pull-request artifacts are not admissible qualification inputs, and selection must remain result-independent.

Creating or downloading an artifact does not consume a performance qualification and does not authorize timing. This contract performs no molecular execution, historical A/B, Fresh-128, public benchmark, product execution, Stage 0 admission, or HIP device run. It creates no reservation and carries no scientific or performance claim.

GitHub Actions has no production authority. It receives no production credential or endpoint access, and neither an Actions identity nor a test double can grant reservation, execution, qualification, or product authority. External authority must still reach blocker zero before any reservation or molecular execution.
