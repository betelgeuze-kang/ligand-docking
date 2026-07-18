# Engine v2 `0.2.0rc1` Release Candidate

## Purpose

`0.2.0rc1` is the first release candidate that combines the post-merge V2-G
contract stack with input identities, docking/benchmark evidence integrity, and
an explicit reference-physics implementation. It remains an internal CPU
reference distribution.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.2.0rc1
Python:       >=3.10,<3.13
PyTorch:      2.6.0
Execution:    CPU reference
```

## Release gates

The release-candidate workflow requires:

- Python 3.10, 3.11, and 3.12 tests;
- focused Ruff correctness checks;
- focused Pyright basic type checks for public contracts;
- AST legacy-import and dense-operation guards;
- two isolated wheel builds with identical `SOURCE_DATE_EPOCH`;
- byte-identical wheel SHA-256 values;
- PEP 561 `py.typed` inclusion;
- clean virtual-environment install and `pip check`;
- import outside the checkout;
- SPDX 2.3 JSON SBOM with the wheel SHA-256 and declared dependencies.

## Implemented but claim-blocked

- strict PDB/SDF bounded ingest and canonical JSON round-trip;
- sparse short-range geometry and periodic image-shift derivatives;
- uncalibrated scalar-energy AI reference model;
- explicit reference bond/angle/torsion/LJ/screened-Coulomb equations;
- deterministic bounded docking proposal/search ledgers;
- typed benchmark metrics, complete failure rows, verified artifacts, and signed
  benchmark reports.

## Promotion blockers

The release candidate must not be promoted as scientifically validated or
customer-ready until independent evidence closes at least the following:

- calibrated and externally reviewed parameter sets;
- applicability-domain evidence;
- force/energy validation against independent references;
- public pose/ranking benchmark results with predeclared protocols;
- GPU numerical and performance parity where acceleration is claimed;
- product route integration, security, deployment, and operator receipts;
- any wetlab or commercial claim-specific evidence.

## Installation smoke

```bash
SOURCE_DATE_EPOCH=1735689600 \
python tools/build_engine_v2_wheel.py --output-dir dist-engine-v2

python -m venv /tmp/engine-v2-rc
/tmp/engine-v2-rc/bin/python -m pip install --upgrade pip
/tmp/engine-v2-rc/bin/python -m pip install cryptography==46.0.5
/tmp/engine-v2-rc/bin/python -m pip install numpy==1.26.4
/tmp/engine-v2-rc/bin/python -m pip install \
  torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
/tmp/engine-v2-rc/bin/python -m pip install --no-deps dist-engine-v2/*.whl
/tmp/engine-v2-rc/bin/python -m pip check
```

## Release decision

A green release-candidate CI proves packaging and contract reproducibility only.
The release candidate preserves these explicit boundaries:

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

GPU parity, public benchmark validation, customer execution approval, and
commercial readiness remain unestablished.
