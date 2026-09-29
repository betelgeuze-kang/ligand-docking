"""Read-only coverage diagnostic for hash-bound native v4 comparison snapshots.

This module uses only the standard library. It inventories recorded metadata;
it does not replay the runtime, rederive the source, fit, score, or admit rows.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, DecimalException, localcontext
import hashlib
import json
import math
from pathlib import Path
import re


SCHEMA = "native_v4_comparison_readiness_diagnostic_v1"
SOURCE_KIND = "native_chembl_receptor_research_v4_fit"
VERSIONS = {
    "installed_native_v4_fit_comparison_frozen_v1": (
        "installed_native_v4_fit_comparison_protocol_v1",
        "installed_native_v4_fit_comparison_result_v1",
    ),
    "installed_native_v4_fit_prepared_comparison_frozen_v2": (
        "installed_native_v4_fit_prepared_comparison_protocol_v2",
        "installed_native_v4_fit_prepared_comparison_result_v2",
    ),
    "installed_native_v4_registered_comparison_frozen_v3": (
        "installed_native_v4_registered_comparison_protocol_v3",
        "installed_native_v4_registered_comparison_result_v3",
    ),
}
REGISTERED_FROZEN = "installed_native_v4_registered_comparison_frozen_v3"
REGISTERED_BACKEND = "registered_pose_fixed_receptor_d3_v1"
REGISTERED_SCORE = "uncalibrated_explicit_graph_scorer_dimensionless_minimize"
REGISTERED_POLICY = "registered_input_single_pose/1.0.0"
REGISTERED_REQUEST = "cpu_registered_pose_fixed_receptor_request/1.0.0"
REGISTERED_DESCRIPTOR = "native_v4_candidate_registered_structural_binding_v1"
REGISTERED_FILES = ("receptor", "ligand", "parameters", "extensions", "cross_parameters")
REGISTERED_FRAME_FIELDS = (
    "schema_version", "target_chembl_id", "receptor_source_sha256", "receptor_system_sha256",
    "receptor_coordinates_sha256", "receptor_construct_sha256", "receptor_cross_parameters_sha256",
    "cross_model_sha256", "pocket_sha256", "coordinate_frame_id", "protocol_settings_sha256",
)
ARMS = ("similarity", "engine", "ai_engine", "similarity_engine")
STATUSES = ("evaluated", "unsupported", "failed", "not_processed")
AUTHORITY_FLAGS = (
    "source_authenticated", "scientifically_validated",
    "same_prepared_assay_state_verified", "product_ranking_enabled",
)
FRAME_FIELDS = (
    "target_chembl_id", "receptor_sources_sha256", "receptor_construct_sha256",
    "pocket_sha256", "evaluation_sha256", "coordinate_frame_id",
    "parameter_source_id", "charge_source_id", "receptor_parameter_sources_sha256",
)
PARAMETER_KEYS = ("protein_atomtypes", "protein_defaults", "ligand_itp",
                  "ligand_atomtypes", "ligand_defaults")
NONFIT_OUTCOME_FIELDS = frozenset({
    "native_activity", "native_activity_origin", "activity_origin", "observation",
    "fit_value", "value", "upper_value", "text_value", "standard_value",
    "standard_upper_value", "standard_text_value", "negative_log10_molar",
    "coordinates", "atom_order", "pose", "environment", "physical_energy", "force_labels",
})
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 10000
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_readiness_json_key")
        result[key] = value
    return result


def _loads(raw):
    def nonfinite(_):
        raise ValueError("nonfinite_readiness_json")
    return json.loads(raw, object_pairs_hook=_object, parse_constant=nonfinite)


def _reference(ref):
    _require(type(ref) is dict and set(ref) == {"path", "sha256"}
             and type(ref["path"]) is str and type(ref["sha256"]) is str
             and SHA.fullmatch(ref["sha256"]) is not None,
             "invalid_readiness_file_reference")
    path = Path(ref["path"])
    _require(path.is_absolute() and path.resolve(strict=True) == path and path.is_file(),
             "readiness_requires_canonical_regular_file")
    return path


class _Inputs:
    def __init__(self):
        self.references = {}

    def read(self, ref, *, jsonl=False):
        path = _reference(ref)
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        _require(len(raw) <= MAX_BYTES, "readiness_input_exceeds_capacity")
        _require(hashlib.sha256(raw).hexdigest() == ref["sha256"],
                 "readiness_input_sha256_mismatch")
        previous = self.references.setdefault(str(path), ref["sha256"])
        _require(previous == ref["sha256"], "conflicting_readiness_file_references")
        if jsonl:
            lines = raw.splitlines()
            _require(1 <= len(lines) <= MAX_ROWS, "readiness_record_capacity_exceeded")
            return [_loads(line) for line in lines]
        return _loads(raw)

    def recheck(self):
        for path, expected in self.references.items():
            ref = {"path": path, "sha256": expected}
            with _reference(ref).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            _require(len(raw) <= MAX_BYTES and hashlib.sha256(raw).hexdigest() == expected,
                     "readiness_input_changed_during_read")


def _index(rows, name):
    _require(type(rows) is list and 1 <= len(rows) <= MAX_ROWS,
             "invalid_readiness_" + name)
    result = {}
    for row in rows:
        _require(type(row) is dict and type(row.get("record_id")) is str
                 and row["record_id"] and row["record_id"] not in result,
                 "duplicate_or_missing_readiness_record_id")
        result[row["record_id"]] = row
    return result


def _identity(row):
    identity = row["chemical_identity"]
    if identity is None:
        return None
    text = identity.get("canonical_isomeric_smiles")
    digest = identity.get("canonical_isomeric_smiles_sha256")
    _require(type(text) is str and text and type(digest) is str
             and hashlib.sha256(text.encode()).hexdigest() == digest,
             "readiness_chemical_identity_hash_mismatch")
    return digest


def _method_key(row):
    """Exact cached method agreement, retaining the intake's exclusion marker."""
    method, meta, origins = row["method_evidence"], row["native_metadata"], row["source_origins"]
    if (not method or origins.get("method_origin") is None
            or "assay_method_not_verified_binding_Ki" in row["admission_issues"]
            or meta["standard_type"] != "Ki" or row["prediction_issues"]):
        return None
    for key in ("assay_chembl_id", "document_chembl_id", "target_chembl_id"):
        if method.get(key) != meta.get(key):
            return None
    if (row["assay_id"] != "chembl:assay:" + meta["assay_chembl_id"]
            or row["target_annotation"]["chembl_target_id"] != meta["target_chembl_id"]):
        return None
    return _sha(method)


def _receptor_sources_sha256(prepared):
    """Hash recorded receptor inputs without opening their source files."""
    def source_hash(ref):
        _require(type(ref) is dict and set(ref) == {"path", "sha256", "source_id"}
                 and type(ref["path"]) is str and Path(ref["path"]).is_absolute()
                 and type(ref["source_id"]) is str and ref["source_id"].strip()
                 and type(ref["sha256"]) is str and SHA.fullmatch(ref["sha256"]),
                 "invalid_readiness_recorded_receptor_source")
        return ref["sha256"]

    chains = prepared["protein_chains"]
    _require(type(chains) is list and 1 <= len(chains) <= MAX_ROWS,
             "invalid_readiness_recorded_receptor_chains")
    projected, chain_ids = [], set()
    single = prepared["schema_version"] == "prepared_gromacs_components_v1"
    for chain in chains:
        field = "molecule_itp" if single else "molecule_itps"
        _require(type(chain) is dict and set(chain) == {"chain_id", field}
                 and type(chain["chain_id"]) is str and len(chain["chain_id"]) <= 1
                 and chain["chain_id"] == chain["chain_id"].strip()
                 and (not single or chain["chain_id"])
                 and chain["chain_id"] not in chain_ids,
                 "invalid_readiness_recorded_receptor_chains")
        chain_ids.add(chain["chain_id"])
        refs = [chain[field]] if single else chain[field]
        _require(type(refs) is list and 1 <= len(refs) <= 32,
                 "invalid_readiness_recorded_receptor_chains")
        projected.append({"chain_id": chain["chain_id"],
                          "molecule_itps_sha256": [source_hash(ref) for ref in refs]})
    _require(prepared["naming_convention"] in {"exact", "pdb_leading_digit_to_gromacs_suffix"}
             and prepared["pdb_element_policy"] in {
                 "reject_missing", "pdb_blank_element_from_matching_topology_atomic_number"},
             "invalid_readiness_recorded_receptor_policy")
    return _sha({
        "schema_version": prepared["schema_version"],
        **{key: source_hash(prepared[key]) for key in (
            "protein_pdb", "protein_atomtypes", "protein_defaults")},
        "protein_chains": projected,
        "naming_convention": prepared["naming_convention"],
        "pdb_element_policy": prepared["pdb_element_policy"],
    })


def _nonfit_outcomes_absent(row, projection):
    _require(row["native_activity"] is None and row["observation"] is None
             and row["eligible_for_point_model"] is False and projection["fit_value"] is None,
             "readiness_nonfit_outcome_present")
    pending = [row]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            for key, item in value.items():
                if key == "primary_evidence":
                    _require(type(item) is dict and not item, "readiness_nonfit_outcome_present")
                elif key in NONFIT_OUTCOME_FIELDS:
                    _require(item is None, "readiness_nonfit_outcome_present")
                pending.append(item)
        elif type(value) is list:
            pending.extend(value)


def _prepared_frame(row, request, recorded, inputs):
    if request is None:
        _require(recorded is None, "readiness_binding_without_prepared_request")
        return None, None
    origin = row["source_origins"].get("prepared_state_origin")
    _require(origin is not None and type(recorded) is dict,
             "readiness_prepared_source_binding_missing")
    _require(row["assigned_role"] == "development_test" and not row["prediction_issues"]
             and row["chemical_identity"] is not None
             and row["assay_id"] == "chembl:assay:" + row["native_metadata"]["assay_chembl_id"]
             and row["target_annotation"]["chembl_target_id"] == row["native_metadata"]["target_chembl_id"],
             "readiness_prepared_source_identity_mismatch")
    _require(request.get("schema_version") == "prepared_rigid_pose_cross_request_v1"
             and request["prepared_input"].get("schema_version") in {
                 "prepared_gromacs_components_v1", "prepared_gromacs_components_v2",
                 "prepared_gromacs_components_v3"}, "unsupported_readiness_prepared_request")
    descriptor = inputs.read(origin)
    _require(descriptor.get("schema_version") == "native_v4_candidate_prepared_structural_binding_v1"
             and recorded == {
                 "schema_version": descriptor["schema_version"],
                 "origin_sha256": origin["sha256"],
                 "observation_sha256": _sha(descriptor),
                 "candidate_prepared_identity_bound": True,
                 "same_prepared_assay_state_verified": False,
             }, "readiness_recorded_prepared_binding_mismatch")
    meta, sources = row["native_metadata"], row["source_origins"]
    _require(all(type(sources.get(key)) is dict for key in ("metadata_origin", "method_origin")),
             "readiness_prepared_metadata_origin_missing")
    expected = {
        "record_id": row["record_id"], "assay_id": row["assay_id"],
        "metadata_origin_sha256": sources["metadata_origin"]["sha256"],
        "method_origin_sha256": sources["method_origin"]["sha256"],
        "target_annotation_sha256": _sha(row["target_annotation"]),
        "target_chembl_id": meta["target_chembl_id"],
        "prepared_input_sha256": _sha(request["prepared_input"]),
        "evaluation_sha256": _sha(request["evaluation"]),
        "pocket_sha256": _sha({key: request["evaluation"][key] for key in (
            "pocket_center_angstrom", "pocket_radius_angstrom")}),
        "parameter_sources_sha256": _sha({key: request["prepared_input"][key]["sha256"]
                                          for key in PARAMETER_KEYS}),
    }
    _require(all(descriptor.get(key) == value for key, value in expected.items())
             and descriptor["ligand"]["canonical_isomeric_smiles_sha256"] == _identity(row)
             and descriptor["ligand"]["formal_charge"] == row["chemical_identity"]["formal_charge"],
             "readiness_prepared_candidate_join_mismatch")
    declarations = request["prepared_input"]["source_declarations"]
    _require(all(descriptor.get(key) == declarations.get(key) for key in (
        "prepared_state_id", "coordinate_frame_id", "parameter_source_id", "charge_source_id")),
        "readiness_prepared_frame_declaration_mismatch")
    # The full receptor-system hash includes ligand-source provenance. Preserve
    # it for audit, but group by receptor-only bytes and their parsing policies.
    receptor_system = descriptor["receptor_system_sha256"]
    _require(type(receptor_system) is str and SHA.fullmatch(receptor_system),
             "invalid_readiness_recorded_receptor_system")
    frame = {key: descriptor[key] for key in FRAME_FIELDS
             if key not in {"receptor_sources_sha256", "receptor_parameter_sources_sha256"}}
    frame["receptor_sources_sha256"] = _receptor_sources_sha256(request["prepared_input"])
    frame["receptor_parameter_sources_sha256"] = _sha({
        key: request["prepared_input"][key]["sha256"] for key in PARAMETER_KEYS[:2]})
    _require(all(type(frame.get(key)) is str and frame[key] for key in FRAME_FIELDS)
             and all(SHA.fullmatch(frame[key]) for key in FRAME_FIELDS if key.endswith("_sha256")),
             "invalid_readiness_recorded_frame")
    return frame, receptor_system


def _recorded_file_reference(ref):
    """Validate a recorded reference without opening a molecular source."""
    _require(type(ref) is dict and set(ref) == {"path", "sha256"}
             and type(ref["path"]) is str and Path(ref["path"]).is_absolute()
             and type(ref["sha256"]) is str and SHA.fullmatch(ref["sha256"]),
             "invalid_readiness_registered_source_reference")


def _registered_input(request, source):
    """Bind recorded adapter input metadata, without constructing its objects."""
    _require(type(source) is dict and type(request) is dict
             and request.get("schema_id") == REGISTERED_REQUEST
             and request.get("backend") == "python_cpu_reference"
             and request.get("solvation") is None
             and source.get("backend") == REGISTERED_BACKEND
             and source.get("request_sha256") == _sha(request)
             and source.get("input_files") == {key: request[key] for key in REGISTERED_FILES}
             and source.get("pose_budget") == request["budget"]
             and source.get("solver") == request["solver"]
             and source.get("score_quantity") == REGISTERED_SCORE
             and source.get("candidate_source_admission_verified") is False
             and source.get("scientifically_validated") is False,
             "readiness_registered_input_binding_mismatch")
    for ref in source["input_files"].values():
        _recorded_file_reference(ref)
    descriptor = source.get("score_descriptor")
    _require(_canonical(descriptor) == _canonical({
        "score_id": "betelgeuze.cpu_explicit_graph_pose_scorer/1.0.0",
        "direction": "minimize", "unit": None,
        "semantics": "uncalibrated_dimensionless_explicit_graph_chemistry_pose_ordering_score",
        "calibrated": False, "reference_method": None,
        "applicability_domain_id": "authenticated_known_pocket_complete_explicit_chemical_graph_partial_charge_v1",
    }), "readiness_registered_score_descriptor_mismatch")
    for key in ("implementation_sha256", "authority_sha256", "parameters_sha256", "cross_parameters_sha256"):
        _require(type(source.get(key)) is str and SHA.fullmatch(source[key]),
                 "invalid_readiness_registered_input_digest")
    proposal = source.get("proposal_policy")
    budget = request["budget"]
    _require(all(type(budget.get(key)) is int and budget[key] >= 0 for key in (
        "candidate_count", "top_k", "max_torsions", "seed", "max_refinement_steps")),
        "readiness_registered_original_pose_binding_mismatch")
    _require(type(proposal) is dict
             and proposal.get("schema_id") == "cpu_registered_input_single_pose_receipt/1.0.0"
             and proposal.get("policy_id") == REGISTERED_POLICY
             and proposal.get("authority_input_receipt_sha256") == source["authority_sha256"]
             and proposal.get("coordinate_frame_id") == request["pocket"]["coordinate_frame_id"]
             and proposal.get("receipt_sha256") == _sha({k: v for k, v in proposal.items() if k != "receipt_sha256"})
             and all(proposal.get(k) == budget[k] for k in (
                 "candidate_count", "top_k", "max_torsions", "translation_radius_angstrom", "seed"))
             and budget["candidate_count"] == budget["top_k"] == 1
             and budget["max_torsions"] == budget["translation_radius_angstrom"] == 0
             and request["comparison"]["require_convergence_for_selection"] is True
             and request["comparison"]["mode"] == "same_candidates",
             "readiness_registered_original_pose_binding_mismatch")
    evaluator, scorer = source.get("evaluator"), source.get("scorer")
    _require(type(evaluator) is dict
             and evaluator.get("evaluator_id") == "cpu_fixed_receptor_reference/1.0.0"
             and evaluator.get("parameter_fingerprint_sha256") == source["parameters_sha256"]
             and evaluator.get("cross_parameters_sha256") == source["cross_parameters_sha256"]
             and evaluator.get("solvation_fingerprint_sha256") is None
             and type(scorer) is dict and set(scorer) == {"feature_model_id", "context", "config", "backend"}
             and scorer["feature_model_id"] == "explicit_graph_hbond_features/1.0.0"
             and all(type(scorer[k]) is str and SHA.fullmatch(scorer[k]) for k in ("context", "config", "backend")),
             "readiness_registered_evaluator_or_scorer_mismatch")


def _registered_frame(row, request, recorded, source, inputs):
    if request is None:
        _require(recorded is None and source is None, "readiness_binding_without_registered_request")
        return None, None
    _registered_input(request, source)
    origin = row["source_origins"].get("prepared_state_origin")
    _require(origin is not None and type(recorded) is dict,
             "readiness_registered_source_binding_missing")
    _require(row["assigned_role"] == "development_test" and _method_key(row) is not None
             and row["chemical_identity"] is not None,
             "readiness_registered_method_or_identity_mismatch")
    descriptor = inputs.read(origin)
    fields = {"schema_version", "record_id", "assay_id", "metadata_origin_sha256", "method_origin_sha256",
              "target_annotation_sha256", "target_chembl_id", "request_schema", "request_sha256",
              "source_files", "ligand", "receptor", "coordinate_frame_id", "pocket_sha256", "charge_origin",
              "charge_policy", "cohort", "same_prepared_assay_state_verified", "source_authenticated",
              "scientifically_validated"}
    _require(type(descriptor) is dict and set(descriptor) == fields
             and descriptor["schema_version"] == REGISTERED_DESCRIPTOR
             and all(descriptor[k] is False for k in (
                 "same_prepared_assay_state_verified", "source_authenticated", "scientifically_validated")),
             "readiness_registered_descriptor_schema_or_authority_mismatch")
    expected = {
        "record_id": row["record_id"], "assay_id": row["assay_id"],
        "metadata_origin_sha256": row["source_origins"]["metadata_origin"]["sha256"],
        "method_origin_sha256": row["source_origins"]["method_origin"]["sha256"],
        "target_annotation_sha256": _sha(row["target_annotation"]),
        "target_chembl_id": row["native_metadata"]["target_chembl_id"],
        "request_schema": REGISTERED_REQUEST, "request_sha256": _sha(request),
        "source_files": source["input_files"], "coordinate_frame_id": request["pocket"]["coordinate_frame_id"],
        "pocket_sha256": _sha(request["pocket"]), "charge_policy": "openmm_xml_decimal_charge_sum_v1",
    }
    _require(all(descriptor[key] == value for key, value in expected.items()),
             "readiness_registered_candidate_join_mismatch")
    _recorded_file_reference(descriptor["charge_origin"])
    ligand, receptor = descriptor["ligand"], descriptor["receptor"]
    _require(type(ligand) is dict and set(ligand) == {"system_sha256", "coordinates_sha256", "atom_graph_sha256",
                "canonical_isomeric_smiles_sha256", "formal_charge", "atom_count"}
             and type(receptor) is dict and set(receptor) == {
                 "system_sha256", "coordinates_sha256", "construct_sha256", "atom_count"}
             and ligand["canonical_isomeric_smiles_sha256"] == _identity(row)
             and type(ligand["formal_charge"]) is int
             and ligand["formal_charge"] == row["chemical_identity"]["formal_charge"]
             and ligand["system_sha256"] == source["proposal_policy"]["source_ligand_system_sha256"]
             and receptor["system_sha256"] == source["evaluator"]["receptor_system_sha256"],
             "readiness_registered_ligand_or_receptor_binding_mismatch")
    for system in (ligand, receptor):
        _require(type(system["atom_count"]) is int and system["atom_count"] > 0
                 and all(type(value) is str and SHA.fullmatch(value)
                         for key, value in system.items() if key.endswith("_sha256")),
                 "invalid_readiness_registered_system_metadata")
    frame = descriptor["cohort"]
    settings = {key: request[key] for key in (
        "schema_id", "backend", "receptor_margin_angstrom", "budget", "solver", "comparison", "selection")}
    _require(type(frame) is dict and set(frame) == set(REGISTERED_FRAME_FIELDS)
             and frame["schema_version"] == "native_v4_registered_prepared_cohort_v1"
             and frame["target_chembl_id"] == descriptor["target_chembl_id"]
             and frame["receptor_source_sha256"] == request["receptor"]["sha256"]
             and frame["receptor_system_sha256"] == receptor["system_sha256"]
             and frame["receptor_coordinates_sha256"] == receptor["coordinates_sha256"]
             and frame["receptor_construct_sha256"] == receptor["construct_sha256"]
             and frame["pocket_sha256"] == descriptor["pocket_sha256"]
             and frame["coordinate_frame_id"] == descriptor["coordinate_frame_id"]
             and frame["protocol_settings_sha256"] == _sha(settings)
             and all(type(value) is str and SHA.fullmatch(value)
                     for key, value in frame.items() if key.endswith("_sha256")),
             "readiness_registered_frame_mismatch")
    _require(set(recorded) == {"schema_version", "origin_sha256", "observation_sha256",
                "candidate_prepared_identity_bound", "same_prepared_assay_state_verified", "cohort",
                "ligand_net_charge_screen", "pose_geometry_status"}
             and recorded.get("schema_version") == REGISTERED_DESCRIPTOR
             and recorded.get("origin_sha256") == origin["sha256"]
             and recorded.get("observation_sha256") == _sha(descriptor)
             and recorded.get("candidate_prepared_identity_bound") is True
             and recorded.get("same_prepared_assay_state_verified") is False
             and recorded.get("cohort") == frame,
             "readiness_recorded_registered_binding_mismatch")
    _registered_initial_status(recorded, ligand["formal_charge"])
    return frame, receptor["system_sha256"]


def _registered_initial_status(receipt, formal_charge):
    """Validate the recorded admission decision; do not read its XML or pose."""
    charge = receipt["ligand_net_charge_screen"]
    fields = {"schema_version", "profile", "status", "rank_eligible", "canonical_formal_charge_sum_e",
              "openmm_printed_partial_charge_sum_e", "difference_e", "print_resolution_bound_e",
              "maximum_rank_difference_e", "charge_tokens_sha256", "mapping_sha256", "xml_sha256", "scope"}
    _require(type(charge) is dict and set(charge) == fields
             and charge["schema_version"] == "registered_openmm_ligand_net_charge_screen_v1"
             and charge["profile"] == "openmm_system_xml_nonbonded_charge_tokens_v1"
             and charge["status"] in {"equal_as_encoded", "within_print_resolution"}
             and charge["rank_eligible"] is True
             and type(charge["canonical_formal_charge_sum_e"]) is int
             and charge["canonical_formal_charge_sum_e"] == formal_charge
             and charge["maximum_rank_difference_e"] == "0.5"
             and type(charge["scope"]) is str and bool(charge["scope"])
             and all(type(charge[k]) is str and SHA.fullmatch(charge[k])
                     for k in ("charge_tokens_sha256", "mapping_sha256", "xml_sha256")),
             "readiness_registered_charge_status_mismatch")
    try:
        numbers = [charge[k] for k in ("openmm_printed_partial_charge_sum_e", "difference_e", "print_resolution_bound_e")]
        _require(all(type(value) is str and len(value) <= 128 for value in numbers),
                 "readiness_registered_charge_status_mismatch")
        total, difference, resolution = map(Decimal, numbers)
        _require(all(value.is_finite() for value in (total, difference, resolution))
                 and all(abs(value.as_tuple().exponent) <= 4096 for value in (total, difference, resolution)),
                 "readiness_registered_charge_status_mismatch")
        with localcontext() as context:
            context.prec = 8192
            _require(difference == total - Decimal(formal_charge) and 0 <= resolution < Decimal("0.5")
                     and (difference == 0 if charge["status"] == "equal_as_encoded"
                          else 0 < abs(difference) <= resolution),
                     "readiness_registered_charge_status_mismatch")
    except DecimalException as exc:
        raise ValueError("readiness_registered_charge_status_mismatch") from exc
    pose = receipt["pose_geometry_status"]
    fields = {"requested", "inside_declared_pocket", "rank_eligible_inside_pocket",
              "cross_distance_unavailable_inside_pocket", "scope"}
    _require(type(pose) is dict and set(pose) == fields
             and all(type(pose[k]) is int for k in fields - {"scope"})
             and pose["requested"] == pose["inside_declared_pocket"] == pose["rank_eligible_inside_pocket"] == 1
             and pose["cross_distance_unavailable_inside_pocket"] == 0
             and type(pose["scope"]) is str and bool(pose["scope"]),
             "readiness_registered_initial_pose_status_mismatch")


def _registered_summary(row, source):
    """Check recorded D3 counters/selection semantics, without report replay."""
    summary = row.get("registered_summary")
    if summary is None:
        _require(row["status"] != "evaluated" and "pose_report" not in row,
                 "readiness_registered_summary_missing")
        return None
    report_ref = row.get("pose_report")
    _require(type(report_ref) is dict and set(report_ref) == {"path", "bytes", "sha256"}
             and report_ref["path"] == f"{row['arm']}/{_sha(row['record_id'])}.poses.json"
             and type(report_ref["bytes"]) is int and report_ref["bytes"] > 0
             and type(report_ref["sha256"]) is str and SHA.fullmatch(report_ref["sha256"])
             and not {"pose_denominator", "numeric_denominator", "selected_pose",
                      "hard_overlap_screen", "ligand_net_charge_screen"}.intersection(row),
             "readiness_registered_report_reference_mismatch")
    _require(type(source) is dict and type(summary) is dict
             and summary.get("status") == row["status"]
             and summary.get("score") == row["score"]
             and summary.get("reason") == row["reason"]
             and summary.get("score_quantity") == REGISTERED_SCORE
             and summary.get("score_descriptor") == source["score_descriptor"]
             and summary.get("proposal_policy_id") == REGISTERED_POLICY
             and all(summary.get(k) is False for k in (
                 "physical_affinity_computed", "candidate_source_admission_verified",
                 "scientifically_validated")), "readiness_registered_summary_mismatch")
    names = ("refinement_attempts", "refinement_failures", "refinement_converged",
             "original_selected_count", "refined_selected_count")
    _require(all(type(summary.get(k)) is int and summary[k] >= 0 for k in names)
             and summary["refinement_attempts"] == 1
             and summary["refinement_failures"] + summary["refinement_converged"] <= 1,
             "readiness_registered_refinement_denominator_mismatch")
    selected = summary.get("selected_candidates")
    _require(type(selected) is list and len(selected) <= 1
             and len(selected) == summary["original_selected_count"] + summary["refined_selected_count"]
             and bool(selected) == (row["status"] == "evaluated"),
             "readiness_registered_selection_mismatch")
    for candidate in selected:
        _require(type(candidate) is dict and candidate.get("variant") in {"baseline", "refined"}
                 and type(candidate.get("score")) in (int, float)
                 and math.isfinite(candidate["score"]) and candidate["score"] == row["score"]
                 and all(candidate.get(k) is True for k in (
                     "pose_valid", "selection_eligible", "validity_complete"))
                 and candidate.get("candidate_id") == source["proposal_policy"]["candidate_id"]
                 and candidate.get("proposal_index") == 0
                 and candidate.get("proposal_fingerprint_sha256") == source["proposal_policy"]["proposal_fingerprint_sha256"],
                 "readiness_registered_selection_mismatch")
    for variant, field in (("baseline", "original_selected_count"), ("refined", "refined_selected_count")):
        _require(sum(c["variant"] == variant for c in selected) == summary[field],
                 "readiness_registered_selection_mismatch")
    _require(summary["refined_selected_count"] <= summary["refinement_converged"],
             "readiness_registered_nonconverged_refinement_selected")
    work = summary.get("work")
    work_fields = {"actual_force_evaluation_calls", "failed_force_evaluation_calls",
                   "score_evaluation_calls", "force_evaluations_reserved", "pose_candidates_in_both_arms"}
    minimum = source["solver"]["minimization"]
    reserve = 1 + source["pose_budget"]["max_refinement_steps"] * (minimum["max_backtracks"] + 1)
    _require(type(work) is dict and set(work) == work_fields
             and all(type(v) is int and v >= 0 for v in work.values())
             and work["force_evaluations_reserved"] == reserve
             and work["failed_force_evaluation_calls"] <= work["actual_force_evaluation_calls"] <= reserve
             and work["score_evaluation_calls"] <= 2
             and work["pose_candidates_in_both_arms"] == 2,
             "readiness_registered_work_denominator_mismatch")
    return {**{key: summary[key] for key in names}, "work": dict(work)}


def _arms(result, frozen, binding):
    pool = frozen["pool"]
    registered = frozen["schema_version"] == REGISTERED_FROZEN
    _require(type(result.get("arms")) is dict and set(result["arms"]) == set(ARMS),
             "readiness_four_arm_set_mismatch")
    answer = {}
    for name in ARMS:
        arm = result["arms"][name]
        completion = arm["completion"]
        _require(type(completion) is dict and completion.get("binding") == binding
                 and completion.get("status") in {
                     "complete", "worker_failed", "budget_exhausted", "interrupted_budget_forfeited"},
                 "readiness_completion_binding_mismatch")
        priority = arm.get("priority")
        _require(priority is None or (type(priority) is dict
                 and priority.get("binding") == binding and priority.get("arm") == name
                 and priority.get("evaluation_labels_read") == 0),
                 "readiness_priority_binding_mismatch")
        rows = arm["rows"]
        _require(list(_index(rows, "arm_rows")) == pool, "readiness_arm_denominator_mismatch")
        by_status = {status: [] for status in STATUSES}
        registered_observations = {}
        for row in rows:
            status, score = row["status"], row["score"]
            _require(status in STATUSES and (
                type(score) in (int, float) and math.isfinite(score)
                if status == "evaluated" else score is None), "invalid_readiness_arm_score")
            summary_only = status in {"unsupported", "not_processed"} and set(row) == {
                "record_id", "status", "score", "reason"}
            _require(summary_only or (row.get("binding") == binding and row.get("arm") == name),
                     "readiness_arm_row_binding_mismatch")
            _require(name == "similarity" or status != "evaluated"
                     or frozen["requests"][row["record_id"]] is not None,
                     "readiness_engine_score_without_prepared_request")
            if registered:
                if name == "similarity":
                    _require("registered_summary" not in row,
                             "readiness_similarity_has_registered_summary")
                else:
                    registered_observations[row["record_id"]] = _registered_summary(
                        row, frozen["source_inputs"][row["record_id"]])
            by_status[status].append(row["record_id"])
        expected = {"requested": len(pool), **dict(Counter(row["status"] for row in rows))}
        _require(arm["denominator"] == expected
                 and all(type(value) is int for value in arm["denominator"].values()),
                 "readiness_recorded_denominator_mismatch")
        _require(set(arm["ranked_record_ids"]) == set(by_status["evaluated"])
                 and len(arm["ranked_record_ids"]) == len(by_status["evaluated"]),
                 "readiness_ranked_candidate_mismatch")
        complete = arm["worker_complete"]
        _require((complete is None and completion["status"] != "complete")
                 or (type(complete) is dict and complete.get("binding") == binding),
                 "readiness_worker_binding_mismatch")
        calls = None if complete is None else complete["engine_calls"]
        _require(calls is None or (type(calls) is int
                 and 0 <= calls <= frozen["protocol"]["max_engine_calls_per_arm"]),
                 "invalid_readiness_recorded_engine_calls")
        _require(calls is None or (calls == 0 if name == "similarity"
                 else calls >= len(by_status["evaluated"])), "readiness_engine_call_count_mismatch")
        _require(arm["score_quantity"] == (
            "predicted_negative_log10_molar_endpoint" if name == "similarity"
            else REGISTERED_SCORE if registered else "existing_cross_only_kcal_per_mol"),
            "readiness_score_quantity_mismatch")
        answer[name] = {
            "status_ids": by_status,
            "denominator": {"requested": len(pool), **{k: len(v) for k, v in by_status.items()}},
            "recorded_engine_calls": calls,
            "score_quantity": arm["score_quantity"],
        }
        if registered and name != "similarity":
            answer[name]["recorded_registered_observations"] = registered_observations
        if registered:
            summaries = [value for value in registered_observations.values() if value is not None]
            work_keys = ("actual_force_evaluation_calls", "failed_force_evaluation_calls",
                         "score_evaluation_calls", "force_evaluations_reserved", "pose_candidates_in_both_arms")
            candidate_calls = 0 if name == "similarity" else calls
            _require(candidate_calls is None or candidate_calls >= len(summaries),
                     "readiness_registered_report_call_count_mismatch")
            recorded_work = {
                "recorded_call_counters": {key: sum(row["work"][key] for row in summaries) for key in work_keys},
                "candidate_reports": len(summaries),
                "candidate_calls_without_returned_report": (
                    None if candidate_calls is None else candidate_calls - len(summaries)),
                "all_candidate_molecular_work_recorded": candidate_calls == len(summaries),
            }
            _require(type(arm.get("registered_work")) is dict
                     and _canonical(arm["registered_work"]) == _canonical(recorded_work),
                     "readiness_registered_arm_work_mismatch")
            answer[name]["recorded_registered_work"] = recorded_work
    return answer


def build(frozen_ref, comparison_ref):
    """Return a snapshot inventory; never write or call the comparator runtime."""
    inputs = _Inputs()
    envelope, result = inputs.read(frozen_ref), inputs.read(comparison_ref)
    _require(type(envelope) is dict and set(envelope) == {"payload", "sha256"}
             and _sha(envelope["payload"]) == envelope["sha256"],
             "readiness_frozen_binding_mismatch")
    frozen, binding = envelope["payload"], envelope["sha256"]
    _require(frozen.get("schema_version") in VERSIONS, "unsupported_readiness_snapshot")
    registered = frozen["schema_version"] == REGISTERED_FROZEN
    protocol_schema, result_schema = VERSIONS[frozen["schema_version"]]
    protocol, pool = frozen["protocol"], frozen["pool"]
    _require(type(pool) is list and 1 <= len(pool) <= MAX_ROWS
             and all(type(rid) is str and rid for rid in pool) and len(set(pool)) == len(pool)
             and protocol["schema_version"] == protocol_schema
             and result["schema_version"] == result_schema and result["binding"] == binding
             and result["pool"] == pool and set(frozen["requests"]) == set(pool)
             and set(protocol["requests"]) == set(pool), "readiness_snapshot_scope_mismatch")
    for value in (frozen, result):
        _require(value.get("source_kind") == SOURCE_KIND and value.get("evaluation_labels_read") == 0
                 and all(value.get(key) is False for key in AUTHORITY_FLAGS),
                 "readiness_snapshot_authority_mismatch")
    source = frozen["source_verification"]
    reference = protocol["source"]
    _require(reference.get("schema_version") == "installed_native_v4_fit_source_reference_v1"
             and reference.get("phase") == "fit"
             and source.get("schema_version") == "installed_native_v4_fit_source_verification_v1"
             and source["source_reference"] == reference
             and source["source_reference_sha256"] == _sha(reference)
             and source["evaluation_labels_read"] == 0,
             "readiness_source_reference_mismatch")
    directory = Path(reference["input_dir"])
    summary_ref = {"path": str(directory / "summary.json"), "sha256": reference["summary_sha256"]}
    summary = inputs.read(summary_ref)
    _require(summary.get("schema_version") == "public_chembl_receptor_development_v4"
             and summary.get("phase") == "fit"
             and summary["records_sha256"] == source["records_sha256"],
             "readiness_source_summary_mismatch")
    records_ref = {"path": str(directory / "records.jsonl"), "sha256": source["records_sha256"]}
    records = inputs.read(records_ref, jsonl=True)
    original, projected = _index(records, "records"), _index(frozen["rows"], "frozen_rows")
    roles = dict(Counter(row["assigned_role"] for row in records))
    counts = {role: roles.get(role, 0) for role in ("fit", "calibration", "development_test")}
    _require(not set(roles) - set(counts) and counts == source["assigned_role_counts"]
             and counts == summary["assigned_role_counts"]
             and len(records) == source["requested_metadata_rows"] == summary["requested_metadata_rows"]
             and list(original) == list(projected)
             and [r["record_id"] for r in records if r["assigned_role"] == "development_test"] == pool,
             "readiness_cached_source_denominator_mismatch")
    for row in records:
        projection = projected[row["record_id"]]
        _require(projection["role"] == row["assigned_role"]
                 and projection["component_id"] == row["component_id"]
                 and projection["assay_id"] == row["assay_id"], "readiness_source_projection_mismatch")
        if row["assigned_role"] != "fit":
            _nonfit_outcomes_absent(row, projection)
    v2 = "prepared_bindings" in frozen
    _require(v2 == (protocol_schema.endswith("_v2") or registered), "readiness_prepared_schema_mismatch")
    if v2:
        _require(set(frozen["prepared_bindings"]) == set(pool)
                 and result["candidate_prepared_identity_bound"] == {
                     rid: frozen["prepared_bindings"][rid] is not None for rid in pool
                 }, "readiness_prepared_binding_denominator_mismatch")
    if registered:
        _require(type(frozen.get("source_inputs")) is dict and set(frozen["source_inputs"]) == set(pool)
                 and type(frozen.get("registered_cohort")) is dict
                 and set(frozen["registered_cohort"]) == {"method_sha256", "frame"},
                 "readiness_registered_cohort_scope_mismatch")
        for rid in pool:
            _require(frozen["requests"][rid] is not None and frozen["prepared_bindings"][rid] is not None,
                     "readiness_registered_candidate_binding_missing")
            _registered_input(frozen["requests"][rid], frozen["source_inputs"][rid])
    arms = _arms(result, frozen, binding)
    common = [rid for rid in pool if all(rid in arms[arm]["status_ids"]["evaluated"] for arm in ARMS)]
    candidates, groups = [], defaultdict(list)
    for rid in pool:
        row, request = original[rid], frozen["requests"][rid]
        identity = _identity(row)
        supported = not row["prediction_issues"] and identity is not None
        _require(projected[rid]["smiles"] == (
            row["chemical_identity"]["canonical_isomeric_smiles"] if supported else None),
            "readiness_candidate_projection_mismatch")
        if request is None:
            _require(protocol["requests"][rid] is None, "readiness_request_presence_mismatch")
        else:
            _require(v2 and inputs.read(protocol["requests"][rid]) == request,
                     "readiness_prepared_request_mismatch")
        if registered:
            frame, receptor_system = _registered_frame(
                row, request, frozen["prepared_bindings"][rid], frozen["source_inputs"][rid], inputs)
            _require(row["native_metadata"]["target_chembl_id"] == "CHEMBL3371"
                     and frozen["registered_cohort"] == {"method_sha256": _method_key(row), "frame": frame},
                     "readiness_registered_strict_method_or_frame_mismatch")
        else:
            frame, receptor_system = _prepared_frame(
                row, request, frozen["prepared_bindings"][rid] if v2 else None, inputs)
        method_key = _method_key(row)
        ki = row["native_metadata"]["standard_type"] == "Ki"
        item = {
            "record_id": rid, "endpoint": row["native_metadata"]["standard_type"],
            "chemical_identity_sha256": identity, "Ki_metadata": ki,
            "selector_supported_in_snapshot": supported,
            "prepared_request_present": request is not None,
            "prepared_source_origin_present": row["source_origins"].get("prepared_state_origin") is not None,
            "recorded_prepared_source_bound": frame is not None,
            "recorded_method_consistent_Ki": method_key is not None,
            "recorded_method_sha256": method_key, "recorded_receptor_pocket_frame": frame,
            "recorded_receptor_system_sha256": receptor_system,
            "in_four_arm_common_scored_set": rid in common,
        }
        candidates.append(item)
        if ki and identity is not None and method_key is not None and frame is not None:
            groups[_sha({"method": method_key, "frame": frame})].append(item)
    if registered:
        _require(len({r["chemical_identity_sha256"] for r in candidates}) >= 2,
                 "readiness_registered_two_distinct_Ki_identities_required")
    cohort_groups = []
    for key, members in sorted(groups.items()):
        observed = [r for r in members if r["in_four_arm_common_scored_set"]]
        cohort_groups.append({
            "group_sha256": key, "record_ids": [r["record_id"] for r in members],
            "distinct_Ki_chemical_identities": len({r["chemical_identity_sha256"] for r in members}),
            "four_arm_common_scored_ids": [r["record_id"] for r in observed],
            "four_arm_common_distinct_Ki_chemical_identities": len({r["chemical_identity_sha256"] for r in observed}),
            "recorded_method_sha256": members[0]["recorded_method_sha256"],
            "recorded_receptor_pocket_frame": members[0]["recorded_receptor_pocket_frame"],
        })
    keys = ("Ki_metadata", "selector_supported_in_snapshot", "prepared_request_present",
            "prepared_source_origin_present", "recorded_prepared_source_bound", "recorded_method_consistent_Ki")
    denominator = {"requested_records": len(pool), **{key: sum(r[key] for r in candidates) for key in keys}}
    denominator.update(
        distinct_recorded_chemical_identities=len({r["chemical_identity_sha256"] for r in candidates if r["chemical_identity_sha256"]}),
        distinct_Ki_chemical_identities=len({r["chemical_identity_sha256"] for r in candidates if r["Ki_metadata"] and r["chemical_identity_sha256"]}),
        unknown_chemical_identity_records=sum(r["chemical_identity_sha256"] is None for r in candidates),
        four_arm_common_scored_records=len(common),
        largest_method_and_frame_group_distinct_Ki_identities=max((g["distinct_Ki_chemical_identities"] for g in cohort_groups), default=0),
        largest_common_method_and_frame_group_distinct_Ki_identities=max((g["four_arm_common_distinct_Ki_chemical_identities"] for g in cohort_groups), default=0),
    )
    inputs.recheck()
    return {
        "schema_version": SCHEMA, "status": "diagnostic_only",
        "scope": "hash_bound_snapshot_metadata_and_recorded_execution_coverage",
        "source_bindings": {"frozen": frozen_ref, "comparison": comparison_ref,
                            "summary": summary_ref, "records": records_ref,
                            "frozen_binding_sha256": binding,
                            "diagnostic_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "requested_pool_ids": pool, "candidates": candidates, "denominator": denominator,
        "arms": arms, "four_arm_common_scored_ids": common,
        "method_and_receptor_pocket_frame_groups": cohort_groups,
        "matching_frame_basis": list(REGISTERED_FRAME_FIELDS if registered else FRAME_FIELDS),
        "method_consistency_basis": "cached_v4_method_support_and_exact_method_metadata_equality",
        **({"recorded_registered_cohort": frozen["registered_cohort"],
            "recorded_candidate_report_schema": "policy_candidate_registered_pose_fixed_receptor_d3_v1",
            "registered_candidate_reports_reverified": False,
            "registered_initial_pose_status_recomputed": False,
            "registered_charge_origin_rederived": False} if registered else {}),
        "score_quantities_combined": False,
        "runtime_replay_verified": False, "raw_source_rederived": False,
        "chemical_identity_recanonicalized": False, "numerical_scores_reverified": False,
        "prepared_systems_reparsed": False, "evaluation_labels_read": 0,
        "model_fit_performed": False, "engine_calls_performed": 0,
        "raw_identity_context_opened": False,
        "scientifically_eligible_comparison_denominator": None,
        **dict.fromkeys(AUTHORITY_FLAGS, False),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", required=True)
    parser.add_argument("--frozen-sha256", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-sha256", required=True)
    args = parser.parse_args(argv)
    result = build({"path": args.frozen, "sha256": args.frozen_sha256},
                   {"path": args.comparison, "sha256": args.comparison_sha256})
    print(_canonical(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
