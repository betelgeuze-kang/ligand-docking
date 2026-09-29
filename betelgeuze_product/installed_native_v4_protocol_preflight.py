"""Opt-in execution preflight for a source-bound native v4 Ki comparison.

This checks whether a proposed v2 protocol can compare distinct development
chemicals in one recorded method and prepared receptor frame. It grants no
assay-state, training, evaluation, or product authority.
"""

from __future__ import annotations

import copy
from pathlib import Path

from . import installed_native_v4_source as source
from . import installed_synthetic_comparison as comparison
from . import native_v4_bound as bound
from .comparison_receipts import ARMS, _sha
from .installed_native_v4_prepared_binding import check_source_binding

SCHEMA = "installed_native_v4_prepared_protocol_preflight_v1"


def _block(code: str, record_id: str | None = None, reason: str | None = None) -> dict:
    result = {"code": code}
    if record_id is not None:
        result["record_id"] = record_id
    if reason is not None:
        result["reason"] = reason
    return result


def _reason(exc: Exception) -> str:
    return str(exc) if type(exc) is ValueError else type(exc).__name__


def _source_hash(ref: dict) -> str:
    if (type(ref) is not dict or set(ref) != {"path", "sha256", "source_id"}
            or type(ref["path"]) is not str or not Path(ref["path"]).is_absolute()
            or type(ref["source_id"]) is not str or not ref["source_id"].strip()
            or type(ref["sha256"]) is not str
            or comparison.HEX.fullmatch(ref["sha256"]) is None):
        raise ValueError("invalid_preflight_receptor_source")
    return ref["sha256"]


def _receptor_sources_sha256(prepared: dict) -> str:
    chains = prepared["protein_chains"]
    if type(chains) is not list or not 1 <= len(chains) <= comparison.MAX_POOL:
        raise ValueError("invalid_preflight_receptor_chains")
    single = prepared["schema_version"] == "prepared_gromacs_components_v1"
    projected, seen = [], set()
    for chain in chains:
        field = "molecule_itp" if single else "molecule_itps"
        if (type(chain) is not dict or set(chain) != {"chain_id", field}
                or type(chain["chain_id"]) is not str
                or chain["chain_id"] in seen):
            raise ValueError("invalid_preflight_receptor_chains")
        seen.add(chain["chain_id"])
        refs = [chain[field]] if single else chain[field]
        if type(refs) is not list or not 1 <= len(refs) <= 32:
            raise ValueError("invalid_preflight_receptor_chains")
        projected.append({"chain_id": chain["chain_id"],
                          "molecule_itps_sha256": [_source_hash(ref) for ref in refs]})
    return _sha({
        "schema_version": prepared["schema_version"],
        **{key: _source_hash(prepared[key]) for key in (
            "protein_pdb", "protein_atomtypes", "protein_defaults")},
        "protein_chains": projected,
        "naming_convention": prepared["naming_convention"],
        "pdb_element_policy": prepared["pdb_element_policy"],
    })


def _method_sha256(row: dict) -> str | None:
    method, metadata = row["method_evidence"], row["native_metadata"]
    if (not method or row["source_origins"].get("method_origin") is None
            or metadata["standard_type"] != "Ki" or row["prediction_issues"]
            or "assay_method_not_verified_binding_Ki" in row["admission_issues"]):
        return None
    if any(method.get(key) != metadata.get(key) for key in (
            "assay_chembl_id", "document_chembl_id", "target_chembl_id")):
        return None
    if (row["assay_id"] != "chembl:assay:" + metadata["assay_chembl_id"]
            or row["target_annotation"]["chembl_target_id"]
            != metadata["target_chembl_id"]):
        return None
    return _sha(method)


def _frame(row: dict, request: dict) -> dict:
    origin = row["source_origins"]["prepared_state_origin"]
    descriptor = bound.bound_json(origin)
    prepared = request["prepared_input"]
    return {
        "target_chembl_id": descriptor["target_chembl_id"],
        "receptor_sources_sha256": _receptor_sources_sha256(prepared),
        "receptor_construct_sha256": descriptor["receptor_construct_sha256"],
        "pocket_sha256": descriptor["pocket_sha256"],
        "evaluation_sha256": descriptor["evaluation_sha256"],
        "coordinate_frame_id": descriptor["coordinate_frame_id"],
        "parameter_source_id": descriptor["parameter_source_id"],
        "charge_source_id": descriptor["charge_source_id"],
        "receptor_parameter_sources_sha256": _sha({
            key: prepared[key]["sha256"] for key in (
                "protein_atomtypes", "protein_defaults")}),
    }


def _supported_execution(execution: object) -> bool:
    if type(execution) is not dict or set(execution) not in (
        {"projection_partition", "preparation_reuse"},
        {"projection_partition", "preparation_reuse", "ligand_size_profile"},
    ):
        return False
    if (execution["projection_partition"] not in ("source_order_v1", "spatial_median_v1")
            or execution["preparation_reuse"] not in ("request", "none")):
        return False
    return ("ligand_size_profile" not in execution
            or execution["ligand_size_profile"] in (
                "standard_256_v1", "extended_512_v1"))


def preflight_v2(protocol: dict) -> dict:
    """Return a runnable frozen protocol or specific fail-closed blockers.

    Existing v1/v2 ``run`` and ``verify-run`` semantics are unchanged. A ready
    result means only that this provided-pose comparison can be attempted.
    """
    result = {
        "schema_version": SCHEMA, "status": "blocked", "blockers": [],
        "protocol": None, "protocol_sha256": None, "frozen_binding_sha256": None,
        "candidate_count": 0, "distinct_Ki_chemical_identity_count": 0,
        "cohort_sha256": None, "assigned_role_counts": None,
        "evaluation_labels_read": 0, "numeric_validation_completed": False,
        "source_authenticated": False, "same_prepared_assay_state_verified": False,
        "scientifically_validated": False, "training_admitted": False,
        "product_ranking_enabled": False,
    }
    if type(protocol) is not dict or protocol.get("schema_version") != comparison.NATIVE_PROTOCOL_V2:
        result["blockers"].append(_block("native_v2_protocol_required"))
        return result
    try:
        verified, scope, rows = source._verified_intake(protocol["source"])
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        result["blockers"].append(_block("source_verification_failed", reason=_reason(exc)))
        return result
    if scope["endpoint"] != "Ki" or scope["target_annotation"] != "CHEMBL3371":
        result["blockers"].append(_block("human_5ht6_Ki_scope_required"))
        return result
    result["assigned_role_counts"] = verified["assigned_role_counts"]
    candidates = [row for row in rows if row["assigned_role"] == "development_test"]
    ids = [row["record_id"] for row in candidates]
    result["candidate_count"] = len(ids)
    requests = protocol.get("requests")
    if type(requests) is not dict or set(requests) != set(ids):
        result["blockers"].append(_block("candidate_request_denominator_mismatch"))
        return result
    if (type(protocol.get("max_engine_calls_per_arm")) is not int
            or protocol["max_engine_calls_per_arm"] < len(ids)):
        result["blockers"].append(_block("engine_call_cap_below_candidate_count"))
    identities, cohorts = set(), set()
    for row in candidates:
        rid = row["record_id"]
        identity = row["chemical_identity"]
        supported_identity = (
            row["native_metadata"]["standard_type"] == "Ki"
            and identity is not None and not row["prediction_issues"]
        )
        if not supported_identity:
            result["blockers"].append(_block("candidate_not_Ki_selector_supported", rid))
        else:
            identities.add(identity["canonical_isomeric_smiles_sha256"])
        method = _method_sha256(row)
        if method is None:
            result["blockers"].append(_block("candidate_method_not_consistent_Ki", rid))
        ref = requests[rid]
        if ref is None:
            result["blockers"].append(_block("prepared_request_missing", rid))
        origin_present = row["source_origins"].get("prepared_state_origin") is not None
        if not origin_present:
            result["blockers"].append(_block("prepared_source_origin_missing", rid))
        if not (supported_identity and method is not None and ref is not None
                and origin_present):
            continue
        try:
            request = comparison._bound_json(ref)
            if not _supported_execution(request.get("execution")):
                result["blockers"].append(_block("prepared_execution_unsupported", rid))
                continue
            binding_receipt = check_source_binding(
                row, request, inspect_pose_geometry=True)
            charge_screen = binding_receipt["ligand_net_charge_screen"]
            if not charge_screen["rank_eligible"]:
                result["blockers"].append(_block(
                    "prepared_ligand_net_charge_rank_ineligible", rid,
                    charge_screen["status"]))
                continue
            pose_status = binding_receipt["pose_geometry_status"]
            if pose_status["inside_declared_pocket"] == 0:
                result["blockers"].append(_block(
                    "prepared_pose_geometry_unusable", rid,
                    f"0/{pose_status['requested']} poses inside declared pocket"))
                continue
            if pose_status["rank_eligible_inside_pocket"] == 0:
                code = ("prepared_pose_cross_distance_unavailable"
                        if pose_status["cross_distance_unavailable_inside_pocket"]
                        else "prepared_pose_hard_overlap_unusable")
                result["blockers"].append(_block(
                    code, rid,
                    f"0/{pose_status['inside_declared_pocket']} in-pocket poses "
                    "pass the 1.0 Å cross-distance ranking screen"))
                continue
            cohorts.add(_sha({"method": method, "frame": _frame(row, request)}))
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            result["blockers"].append(_block("prepared_source_binding_failed", rid,
                                              _reason(exc)))
    result["distinct_Ki_chemical_identity_count"] = len(identities)
    if len(identities) < 2:
        result["blockers"].append(_block("two_distinct_Ki_chemical_identities_required"))
    if len(cohorts) > 1:
        result["blockers"].append(_block("method_or_receptor_pocket_frame_mismatch"))
    if result["blockers"]:
        return result
    try:
        frozen = comparison.freeze(protocol)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        result["blockers"].append(_block("comparison_freeze_failed", reason=_reason(exc)))
        return result
    if (set(frozen["pool"]) != set(ids)
            or set(frozen["prepared_bindings"]) != set(ids)
            or any(frozen["prepared_bindings"][rid] is None for rid in ids)
            or set(protocol["arm_order"]) != set(ARMS)):
        result["blockers"].append(_block("frozen_candidate_or_arm_mismatch"))
        return result
    result.update(status="ready", protocol=copy.deepcopy(frozen["protocol"]),
                  protocol_sha256=_sha(frozen["protocol"]),
                  frozen_binding_sha256=_sha(frozen), cohort_sha256=next(iter(cohorts)))
    return result
