"""Bind a saved v3 prepared cross report to its unchanged local request files.

This verifier replays input parsing and canonical serialization, not an energy
calculation. The separate scalar checker remains the numerical reference. A
prepared file is not evidence that it came from a particular crystal structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
from betelgeuze_engine.product import v2_cross_interaction as adapter
from betelgeuze_engine.product.v2_cross_interaction import MINIMUM_PAIR_DISTANCE_ANGSTROM, SCHEMA_ID
from betelgeuze_engine_v2.molecular import canonical_coordinates_sha256, canonical_system_document
from betelgeuze_engine_v2.molecular.serialization import canonical_json_value, canonical_system_sha256
from tools.product import score_prepared_cross_interactions as consumer


REQUEST_LIMIT = 16 * 1024 * 1024
REPORT_LIMIT = 256 * 1024 * 1024
PREPARED_FILE_LIMIT = 16 * 1024 * 1024
EVALUATION_FIELDS = {
    "pocket_center_angstrom", "pocket_radius_angstrom", "cutoff_angstrom",
    "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom",
}
REPORT_FIELDS = {
    "schema_version", "rows", "denominator", "customer_execution",
    "scientifically_validated", "external_solver_called", "request_sha256",
    "consumer_source_sha256", "environment", "process_observation", "exit_code",
}
RESULT_FIELDS = {
    "schema_id", "status", "source_declarations", "model", "sources",
    "pocket", "quantities", "unevaluated_reason", "source_zero_sigma_projection",
    "zero_sigma_projection_reason", "pair_accounting", "cost",
    "adapter_source_sha256", "uncertainty", "uncertainty_calibrated",
    "scientifically_validated", "customer_execution", "external_solver_called",
}


class PreparedReportBindingError(ValueError):
    """The saved report cannot be bound to the supplied prepared file bytes."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PreparedReportBindingError(reason)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise PreparedReportBindingError("nonfinite_json_constant:" + value)


def _load(path: Path, limit: int) -> tuple[dict, str]:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _require(len(raw) <= limit, "input_capacity_exceeded")
    value = json.loads(raw, object_pairs_hook=_object, parse_constant=_reject_nonfinite)
    _require(type(value) is dict, "json_object_required")
    return value, hashlib.sha256(raw).hexdigest()


def _still_same(path: Path, digest: str, limit: int) -> bool:
    observed = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                count += len(block)
                if count > limit:
                    return False
                observed.update(block)
    except OSError:
        return False
    return observed.hexdigest() == digest


def _json(value) -> str:
    # JSON comparison retains numeric type and signed-zero distinctions that
    # ordinary Python dict equality would erase.
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _same(actual, expected, reason: str) -> None:
    _require(_json(actual) == _json(expected), reason)


def _number(value, label: str, minimum: float | None = None) -> float:
    _require(type(value) in {int, float}, "invalid_evaluation:" + label)
    number = float(value)
    _require(math.isfinite(number) and (minimum is None or number >= minimum),
             "invalid_evaluation:" + label)
    return number


def _evaluation(value: dict, ligand) -> tuple[dict, dict]:
    _require(type(value) is dict and set(value) == EVALUATION_FIELDS,
             "incomplete_evaluation")
    center = value["pocket_center_angstrom"]
    _require(type(center) is list and len(center) == 3, "invalid_pocket_center")
    center = [_number(item, "pocket_center") for item in center]
    radius = _number(value["pocket_radius_angstrom"], "pocket_radius", 0.0)
    cutoff = _number(value["cutoff_angstrom"], "cutoff", 0.0)
    start = _number(value["switch_start_angstrom"], "switch_start", 0.0)
    dielectric = _number(value["dielectric"], "dielectric", 0.0)
    kappa = _number(value["screening_kappa_per_angstrom"], "screening_kappa", 0.0)
    _require(radius > 0 and 0 < start < cutoff <= 20
             and cutoff >= MINIMUM_PAIR_DISTANCE_ANGSTROM and dielectric > 0,
             "invalid_evaluation_domain")
    for point in ligand.coordinates[0].tolist():
        _require(math.dist(point, center) <= radius, "ligand_outside_declared_pocket")
    model = {
        "id": "existing_v2_switched_cross_lj_screened_coulomb_v1",
        "cutoff_angstrom": cutoff, "switch_start_angstrom": start,
        "dielectric": dielectric, "screening_kappa_per_angstrom": kappa,
        "mixing": "Lorentz-Berthelot", "cross_pair_scaling": 1.0,
        "periodic": False, "source_full_simulation_hamiltonian_reproduced": False,
        "minimum_pair_distance_angstrom": MINIMUM_PAIR_DISTANCE_ANGSTROM,
        "minimum_distance_scope": "all source atoms; admission independent of tile order",
    }
    return model, {"center_angstrom": center, "radius_angstrom": radius}


def _source(system, parameters) -> dict:
    return {
        "system_sha256": canonical_system_sha256(system),
        "coordinates_sha256": canonical_coordinates_sha256(system),
        "system": canonical_json_value(canonical_system_document(system)),
        "nonbonded_parameters": parameters,
    }


def _request_source_refs(request: dict):
    """Enumerate every v3 file slot, including ordered protein molecules."""
    fields = ("protein_pdb", "protein_atomtypes", "protein_defaults",
              "ligand_sdf", "ligand_gro", "ligand_itp",
              "ligand_atomtypes", "ligand_defaults")
    for case in request["cases"]:
        prepared = case["prepared_input"]
        for key in fields:
            yield prepared[key]
        for chain in prepared["protein_chains"]:
            yield from chain["molecule_itps"]


def _request_sources_still_same(request: dict) -> bool:
    return all(_still_same(Path(ref["path"]), ref["sha256"], PREPARED_FILE_LIMIT)
               for ref in _request_source_refs(request))


def verify_binding(request: dict, report: dict, *, request_sha256: str) -> dict:
    """Verify saved producer inputs against the current v3 reader, without scoring."""
    _require(type(request) is dict and set(request) == {"schema_version", "cases"}
             and request["schema_version"] in {consumer.SCHEMA, consumer.SCHEMA_V2}
             and type(request["cases"]) is list and 1 <= len(request["cases"]) <= 32,
             "unsupported_prepared_request")
    version_two = request["schema_version"] == consumer.SCHEMA_V2
    expected_report_schema = ("prepared_cross_interaction_report_v2" if version_two
                              else "prepared_cross_interaction_report_v1")
    _require(type(report) is dict and set(report) == REPORT_FIELDS
             and report["schema_version"] == expected_report_schema,
             "unsupported_saved_report_or_unmapped_claim")
    _require(report["request_sha256"] == request_sha256, "request_hash_mismatch")
    _require(report["consumer_source_sha256"] == hashlib.sha256(
        Path(consumer.__file__).read_bytes()).hexdigest(), "consumer_source_mismatch")
    _require(report["customer_execution"] is False
             and report["scientifically_validated"] is False
             and report["external_solver_called"] is False
             and type(report["exit_code"]) is int and report["exit_code"] == 0,
             "unsupported_authority_or_incomplete_execution")
    rows, cases = report["rows"], request["cases"]
    _require(type(rows) is list and len(rows) == len(cases)
             and report["denominator"] == {"requested": len(cases), "evaluated": len(cases),
                                            "failed": 0, "skipped": 0},
             "report_denominator_mismatch")
    identities = []
    source_refs = {}
    for index, (case, row) in enumerate(zip(cases, rows)):
        fields = {"case_id", "prepared_input", "evaluation"} | ({"execution"} if version_two else set())
        _require(type(case) is dict and set(case) == fields
                 and type(case["case_id"]) is str and bool(case["case_id"].strip()),
                 "invalid_case")
        prepared = case["prepared_input"]
        _require(type(prepared) is dict
                 and prepared.get("schema_version") == "prepared_gromacs_components_v3",
                 "prepared_v3_required")
        row_fields = {"request_index", "case_id", "source_geometry_observation",
                      "preparation_provenance", "status", "result", "cost"}
        if version_two:
            row_fields.add("execution")
        _require(type(row) is dict and set(row) == row_fields
                 and type(row["request_index"]) is int and row["request_index"] == index
                 and row["case_id"] == case["case_id"] and row["status"] == "evaluated",
                 "report_case_identity_or_status_mismatch")
        if version_two:
            execution = case["execution"]
            _require(type(execution) is dict and set(execution) in (
                {"projection_partition"}, {"projection_partition", "ligand_size_profile"})
                and execution["projection_partition"] in {"source_order_v1", "spatial_median_v1"}
                and execution.get("ligand_size_profile", "standard_256_v1") in {
                    "standard_256_v1", "extended_512_v1"}, "unsupported_execution")
            _same(row["execution"], execution, "execution_mismatch")
        receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(prepared)
        _require(provenance["source_hashes_postflight_verified"] is True
                 and provenance["declarations_verified"] is False
                 and provenance["source_coevality_verified"] is False,
                 "unsupported_prepared_source_claim")
        for source in provenance["sources"].values():
            previous = source_refs.setdefault(source["path"], source["sha256"])
            _require(previous == source["sha256"], "same_path_conflicting_prepared_hashes")
        _same(row["preparation_provenance"], provenance, "preparation_provenance_mismatch")
        observation = row["source_geometry_observation"]
        _require(type(observation) is dict
                 and observation.get("physical_validity_assessed") is False
                 and observation.get("affects_score_or_admission") is False
                 and observation.get("scientifically_validated") is not True,
                 "unsupported_geometry_authority_claim")
        result = row["result"]
        expected_result_fields = RESULT_FIELDS | ({"input_domain"} if version_two
                                                  and case["execution"].get("ligand_size_profile") == "extended_512_v1"
                                                  else set())
        _require(type(result) is dict and set(result) == expected_result_fields
                 and result.get("schema_id") == SCHEMA_ID
                 and result.get("status") == "evaluated"
                 and result.get("scientifically_validated") is False
                 and result.get("customer_execution") is False
                 and result.get("external_solver_called") is False
                 and result.get("uncertainty") is None
                 and result.get("uncertainty_calibrated") is False
                 and result.get("adapter_source_sha256") == hashlib.sha256(
                     Path(adapter.__file__).read_bytes()).hexdigest(),
                 "unsupported_result_or_authority_claim")
        _same(result["source_declarations"], prepared["source_declarations"],
              "source_declarations_mismatch")
        model, pocket = _evaluation(case["evaluation"], ligand)
        _same(result["model"], model, "model_mismatch")
        _same(result["pocket"], pocket, "pocket_mismatch")
        _same(result["sources"], {"receptor": _source(receptor, rp),
                                   "ligand": _source(ligand, lp)}, "canonical_sources_mismatch")
        accounting = result["pair_accounting"]
        _require(type(accounting) is dict
                 and type(accounting.get("requested_cross_pairs")) is int
                 and accounting["requested_cross_pairs"] == receptor.atom_count * ligand.atom_count
                 and type(accounting.get("receptor_atoms")) is int
                 and accounting["receptor_atoms"] == receptor.atom_count
                 and type(accounting.get("ligand_atoms")) is int
                 and accounting["ligand_atoms"] == ligand.atom_count,
                 "source_pair_denominator_mismatch")
        partition = (case["execution"]["projection_partition"] if version_two
                     else "source_order_v1")
        if partition == "source_order_v1":
            _require("projection_partition" not in accounting,
                     "unexpected_projection_partition_claim")
        else:
            projection = accounting.get("projection_partition")
            _require(type(projection) is dict
                     and projection.get("requested") == partition,
                     "projection_partition_request_mismatch")
        profile = (case["execution"].get("ligand_size_profile", "standard_256_v1")
                   if version_two else "standard_256_v1")
        if profile == "extended_512_v1":
            _same(result["input_domain"], {
                "ligand_size_profile": profile,
                "max_ligand_atoms": adapter.EXTENDED_MAX_LIGAND_ATOMS,
                "max_receptor_atoms": adapter.MAX_RECEPTOR_ATOMS,
                "scope": "input size only; unchanged tiled kernel and numerical guards",
            }, "input_domain_mismatch")
        quantities = result["quantities"]
        _require(type(quantities) is dict and set(quantities) == {
            "cross_lennard_jones_kcal_per_mol", "cross_screened_coulomb_kcal_per_mol",
            "cross_total_kcal_per_mol", "receptor_cross_forces_kcal_per_mol_angstrom",
            "ligand_cross_forces_kcal_per_mol_angstrom", "internal_energy",
            "strain", "solvation", "residual", "affinity",
        } and all(quantities.get(key) is None for key in (
            "internal_energy", "strain", "solvation", "residual", "affinity")),
            "unsupported_non_cross_quantity_claim")
        identities.append({
            "request_index": index, "case_id": case["case_id"],
            "receptor_system_sha256": canonical_system_sha256(receptor),
            "ligand_system_sha256": canonical_system_sha256(ligand),
            "prepared_source_sha256": {key: source["sha256"]
                                       for key, source in provenance["sources"].items()},
        })
    for path, digest in source_refs.items():
        _require(_still_same(Path(path), digest, PREPARED_FILE_LIMIT),
                 "prepared_source_changed_during_binding")
    return {
        "schema_version": "prepared_cross_report_binding_v1", "status": "passed",
        "denominator": {"requested": len(cases), "bound": len(cases), "not_bound": 0},
        "rows": identities, "request_sha256": request_sha256,
        "prepared_file_hashes_verified": True, "saved_report_binding_verified": True,
        "original_structure_lineage_verified": False,
        "source_declarations_verified": False, "source_coevality_verified": False,
        "numeric_comparison_performed": False, "physical_validity_assessed": False,
        "scientifically_validated": False, "training_admitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must be a new path")
    request, request_sha = _load(args.request, REQUEST_LIMIT)
    report, report_sha = _load(args.report, REPORT_LIMIT)
    try:
        result = verify_binding(request, report, request_sha256=request_sha)
        _require(_still_same(args.request, request_sha, REQUEST_LIMIT)
                 and _still_same(args.report, report_sha, REPORT_LIMIT),
                 "request_or_report_changed_during_verification")
        _require(_request_sources_still_same(request),
                 "prepared_source_changed_after_verification")
        code = 0
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        requested = (len(request.get("cases", []))
                     if type(request.get("cases")) is list else None)
        result = {
            "schema_version": "prepared_cross_report_binding_v1", "status": "not_bound",
            "reason": str(exc), "error_type": type(exc).__name__,
            "denominator": {"requested": requested, "bound": 0,
                            "not_bound": requested},
            "prepared_file_hashes_verified": False, "saved_report_binding_verified": False,
            "original_structure_lineage_verified": False,
            "source_declarations_verified": False, "source_coevality_verified": False,
            "numeric_comparison_performed": False, "physical_validity_assessed": False,
            "scientifically_validated": False, "training_admitted": False,
        }
        code = 2
    result["report_sha256"] = report_sha
    result["verifier_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
