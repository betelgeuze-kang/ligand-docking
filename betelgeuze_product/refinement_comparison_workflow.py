"""Opt-in local CPU docking/refinement comparison; no product admission or MD.

Usage: python -m betelgeuze_product.refinement_comparison_workflow REQUEST --output NEW_DIR
Inputs are SHA-bound canonical systems and COMPLETE explicit reference parameters.
Existing directories are never overwritten and historical checkpoints are not read.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import hashlib
import math
from pathlib import Path
import platform

import torch

from betelgeuze_engine_v2.docking import (
    DockingBudget, DockingScope, PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig, run_cpu_refinement_comparison,
)
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import _config_from_document
from .local_research_workflow import _decode, _json
from .reference_minimization_workflow import _bound, _directory, _parameters, _publish, _read

SCHEMA_ID = "cpu_refinement_comparison_request/1.0.0"


def _source_manifest() -> dict[str, str]:
    import betelgeuze_engine_v2
    root = Path(betelgeuze_engine_v2.__file__).resolve().parent
    paths = sorted(root.rglob("*.py"))
    selected = {"betelgeuze_engine_v2/" + p.relative_to(root).as_posix(): p for p in paths}
    product_root = Path(__file__).resolve().parent
    # This opt-in closure is deliberately separate from the frozen engine
    # manifest. Relocating modules must never exclude their bytes from evidence.
    for path in sorted((product_root / "cpu_refinement").rglob("*.py")):
        selected["betelgeuze_product/" + path.relative_to(product_root).as_posix()] = path
    for name in ("__init__.py", "refinement_comparison_workflow.py", "reference_minimization_workflow.py",
                 "local_research_workflow.py"):
        selected["betelgeuze_product/" + name] = Path(__file__).resolve().parent / name
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in selected.items()}


def _load(request, source_digest):
    expected = {"schema_id", "backend", "receptor", "ligand", "parameters", "pocket",
                "receptor_margin_angstrom", "budget", "minimization", "comparison"}
    if (type(request) is not dict or set(request) != expected
            or request["schema_id"] != SCHEMA_ID or request["backend"] != "python_cpu_reference"):
        raise ValueError("explicit CPU refinement comparison request required")
    receptor = all_atom_system_from_canonical_json(_json(_bound(request["receptor"])))
    ligand = all_atom_system_from_canonical_json(_json(_bound(request["ligand"])))
    for system, maximum in ((receptor, 8192), (ligand, 256)):
        if (system.model_count != 1 or not 1 <= system.atom_count <= maximum
                or system.coordinates.device.type != "cpu"
                or system.coordinates.dtype != torch.float64 or system.cell is not None):
            raise ValueError("bounded single-model nonperiodic CPU binary64 system required")
    parameters = _parameters(_bound(request["parameters"]))
    minimization = _config_from_document(request["minimization"])
    if minimization.to_dict() != request["minimization"]:
        raise ValueError("noncanonical minimization configuration")
    row = request["budget"]
    if type(row) is not dict or set(row) != {f.name for f in fields(DockingBudget)}:
        raise ValueError("complete docking budget required")
    for name, value in row.items():
        if name == "translation_radius_angstrom":
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("finite translation radius required")
        elif type(value) is not int:
            raise ValueError("exact integer docking budget required")
    budget = DockingBudget(**row)
    if budget.candidate_count > 64:
        raise ValueError("local comparison supports at most 64 candidates per arm")
    comp = request["comparison"]
    if type(comp) is not dict or set(comp) != {f.name for f in fields(RefinementComparisonConfig)}:
        raise ValueError("complete comparison configuration required")
    comparison = RefinementComparisonConfig(**comp)
    pocket = request["pocket"]
    pocket_fields = {"center_angstrom", "radius_angstrom", "coordinate_frame_id",
                     "source_artifact_sha256", "method_id", "method_version"}
    if type(pocket) is not dict or set(pocket) != pocket_fields:
        raise ValueError("explicit known pocket required")
    if (type(pocket["center_angstrom"]) is not list or len(pocket["center_angstrom"]) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in pocket["center_angstrom"])):
        raise ValueError("finite three-dimensional pocket center required")
    for value in (pocket["radius_angstrom"], request["receptor_margin_angstrom"]):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0.:
            raise ValueError("positive finite pocket radius and receptor margin required")
    definition = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        center=torch.tensor(pocket["center_angstrom"], dtype=torch.float64),
        radius_angstrom=pocket["radius_angstrom"],
        coordinate_frame_id=pocket["coordinate_frame_id"],
        source_artifact_sha256=pocket["source_artifact_sha256"],
        method_id=pocket["method_id"], method_version=pocket["method_version"],
        implementation_source_sha256=source_digest,
    )
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, definition, receptor_margin_angstrom=request["receptor_margin_angstrom"])
    return authority, receptor, ligand, parameters, budget, minimization, comparison


def run_request(request: dict, output: str | Path) -> dict:
    request = _decode(_json(request))
    sources = _source_manifest()
    source_digest = hashlib.sha256(_json(sources).encode()).hexdigest()
    authority, receptor, ligand, parameters, budget, minimization, comparison = _load(request, source_digest)
    with _directory(output, resume=False) as directory:
        _publish(directory / "request.json", request)
        result = run_cpu_refinement_comparison(
            authority, budget, receptor_system=receptor, ligand_system=ligand,
            parameters=parameters, implementation_source_sha256=source_digest,
            minimization=minimization, comparison=comparison,
        )
        # Verify current bytes again; a changed input cannot become a successful report.
        for name in ("receptor", "ligand", "parameters"):
            _bound(request[name])
        if _source_manifest() != sources:
            raise ValueError("implementation source changed during execution")
        report = {
            "schema_id": "local_cpu_refinement_comparison_result/1.0.0",
            "request_sha256": hashlib.sha256(_json(request).encode()).hexdigest(),
            "implementation_sources": sources,
            "implementation_source_sha256": source_digest,
            "environment": {"python": platform.python_version(), "torch": str(torch.__version__),
                            "torch_threads": torch.get_num_threads(), "platform": platform.platform()},
            "result": result,
        }
        _publish(directory / "report.json", report)
        _publish(directory / "complete.json", {
            "report_sha256": hashlib.sha256((_json(report) + "\n").encode()).hexdigest(),
            "execution_complete": True, "scientifically_validated": False,
            "candidate_failure_count": result["baseline"]["failure_count"] + result["refined"]["failure_count"],
        })
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    request = _decode(_read(args.request.absolute()))
    report = run_request(request, args.output)
    print(_json({"output": str(args.output.absolute()), "report_sha256": report["result"]["report_sha256"],
                 "mode": report["result"]["mode"], "scientifically_validated": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
