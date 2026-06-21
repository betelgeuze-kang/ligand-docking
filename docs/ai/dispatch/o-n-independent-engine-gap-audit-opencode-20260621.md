# OpenCode worker slice: O(N) independent engine gap audit

You are a scoped implementation worker for Codex in `betelgeuze-kang/ligand-docking`.

Mode: read-only audit. Do not edit files. Do not stage, commit, push, delete, run cleanup, mutate GitHub, or access external network.

Safety:
- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not inspect CASP active author codes or public/template/native target data.
- Do not use web search.
- Avoid vendored/heavy paths such as `tools/bin/**`, `.betelgeuze/**`, `runs/**`, `.git/**`, `casp17/**`.

Goal:
Audit the current repository against the new P0 objective: product runtime must avoid NxN neighbor tensors and use a bounded O(N)-near neighbor provider under fixed density/cutoff.

Focus paths:
- `betelgeuze_engine/physics/**`
- `betelgeuze_engine/benchmark/**`
- `betelgeuze_engine/validation/**`
- `core/rust_hip_backend.py`
- `rust_engine/src/**`
- `tools/product/**`
- `api/**`
- `.github/workflows/**`
- `tests/unit/**` only for tests directly relevant to neighbor/scaling/claim gates

Return at most 80 lines with:
1. Product path NxN/full-pair usage locations, with file:line and why each is or is not product-blocking.
2. Existing Rust/HIP neighbor builder capabilities and gaps versus Python reference.
3. Existing benchmark/gate coverage for neighbor scaling, memory, pair parity, and claim/EvidenceBundle gate.
4. P0 blockers ordered by severity.
5. Suggested first code slice that can be implemented safely next.

Do not include full logs or full diffs.
