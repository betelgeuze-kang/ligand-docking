# Dependency Matrix

This matrix explains where the reviewer-facing dependency surfaces place the
main runtime, API, chemistry, and molecular-dynamics dependencies. It is based
on the current top-level files:

- `requirements-package.txt`
- `requirements.txt`
- `requirements-api.txt`
- `requirements-dev.txt`
- `pyproject.toml`

`pyproject.toml` uses dynamic project dependencies from
`requirements-package.txt`, so installable package dependencies should be read
through that file rather than duplicated in `pyproject.toml`.

## Matrix

| Dependency family | `requirements-package.txt` | `requirements.txt` | `requirements-api.txt` | `requirements-dev.txt` | `pyproject.toml` | Current role |
| --- | --- | --- | --- | --- | --- | --- |
| `torch` | no | `torch==2.6.0` | no | inherited through `requirements.txt` | no direct pin | Core local runtime / physics path. Not part of the installable package dependency file. |
| `fastapi` | no | no | `fastapi` | no | no direct pin | Optional product API server profile only. |
| `uvicorn` | no | no | `uvicorn[standard]` | no | no direct pin | Optional product API server runner only. |
| `pydantic` | `pydantic==2.12.5` | inherited through `requirements-base.txt` | indirect runtime companion via API stack; `pydantic-settings` is explicit | inherited through `requirements.txt` | dynamic via `requirements-package.txt` | Shared runtime/config/schema dependency and installable package dependency. |
| `pydantic-settings` | no | no | `pydantic-settings` | no | no direct pin | Optional product API configuration dependency. |
| `rdkit` / `rdkit-pypi` | no | no | no | no | no direct pin | Chemistry/backmapping/product-runner capability dependency, but not in these five files. Current pinned product ROCm profile is `requirements-product-rocm.txt` with `rdkit-pypi==2022.9.5`. |
| `openmm` | no | no | no | no | no direct pin | External/reference MD artifact and optional force-field/minimization dependency. Not pinned in these five files. |
| `openff.toolkit`, `openmmforcefields`, `pdbfixer` | no | no | no | no | no direct pin | Optional full-forcefield repair/probe ecosystem. Not part of the default package, runtime, API, or dev install surface. |

## Read The Files This Way

- `requirements-package.txt` is the installable package dependency contract used
  by `pyproject.toml`. Keep this file small and source-compatible.
- `requirements.txt` is the default local runtime profile. It imports
  `requirements-base.txt` and adds `torch==2.6.0`.
- `requirements-api.txt` is intentionally optional. It is for the FastAPI
  product surface and should not be required for offline local delivery.
- `requirements-dev.txt` imports the default runtime profile and adds test
  tooling.
- RDKit/OpenMM-style dependencies are capability-specific. A reviewer should not
  infer that clean `pip install -r requirements.txt` is enough to regenerate
  every chemistry, all-atom, or OpenMM evidence artifact.

## Practical Reviewer Installs

| Reviewer goal | Install input | Expected dependency coverage |
| --- | --- | --- |
| Default offline runtime/tests | `pip install -r requirements.txt && pip install -r requirements-dev.txt` | Base runtime, Torch CPU/default wheel, pytest. |
| Product API smoke | `pip install -r requirements-api.txt` in addition to runtime deps | FastAPI, Uvicorn, API config helpers, API HTTP test helper. |
| Installable CLI/package audit | `pip install -e .` | Dynamic dependencies from `requirements-package.txt`. |
| RDKit chemistry/backmapping paths | Capability profile or environment that provides RDKit; see `requirements-product-rocm.txt` for the current pinned product ROCm entry | RDKit-backed ligand topology, chemistry states, ETKDG/backmapping, and selected product-runner checks. |
| OpenMM/all-atom reference replay | External OpenMM-capable environment plus required local artifacts/manifests | OpenMM reference/minimization evidence. This is not a default clean-clone dependency. |

## Guardrail

Do not silently move API, RDKit, OpenMM, or full-forcefield dependencies into the
default runtime/package surface just to make a broad claim look installable. If
a lane needs those dependencies, document it as a lane-specific profile and
record the resulting environment in the generated evidence bundle.
