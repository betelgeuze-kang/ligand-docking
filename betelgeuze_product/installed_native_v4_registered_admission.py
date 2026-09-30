"""Shared fail-closed admission for the registered-pose comparison protocol.

The caller first rederives the native FIT-only intake and role separation.
These checks bind development candidates to prepared inputs without admitting
experimental labels, assigning roles, or executing score_terms, force evaluation, or minimization. Scorer setup
includes reference intraligand arithmetic.
"""

from __future__ import annotations

from collections import Counter
import json

from .comparison_receipts import _sha
from .installed_native_v4_protocol_preflight import _method_sha256


class RegisteredAdmissionError(ValueError):
    """Keep the verified candidate denominator when admission is blocked."""

    def __init__(self, result):
        self.report = {key: result[key] for key in (
            "blockers", "candidate_count", "distinct_Ki_chemical_identity_count",
            "assigned_role_counts")}
        super().__init__("registered_candidate_admission_blocked:" + json.dumps(
            result["blockers"], sort_keys=True, separators=(",", ":")))


def inspect_candidates(protocol: dict, source_rows: list[dict]) -> dict:
    from . import installed_synthetic_comparison as comparison
    from .installed_native_v4_registered_binding import check_source_binding
    from .cpu_refinement_v1_2 import registered_policy_adapter as adapter

    result = {"blockers": [], "requests": {}, "source_inputs": {},
              "prepared_bindings": {}, "cohort": None,
              "distinct_Ki_chemical_identity_count": 0}
    candidates = [row for row in source_rows
                  if row["assigned_role"] == "development_test"]
    ids = [row["record_id"] for row in candidates]
    result["candidate_count"] = len(candidates)
    counts = Counter(row["assigned_role"] for row in source_rows)
    result["assigned_role_counts"] = {role: counts[role] for role in (
        "fit", "calibration", "development_test")}
    identities = {
        row["chemical_identity"]["canonical_isomeric_smiles_sha256"]
        for row in candidates
        if row["native_metadata"]["standard_type"] == "Ki"
        and row["target_annotation"]["chembl_target_id"] == "CHEMBL3371"
        and row["chemical_identity"] is not None and not row["prediction_issues"]
    }
    result["distinct_Ki_chemical_identity_count"] = len(identities)

    def block(code, rid=None, reason=None):
        item = {"code": code}
        if rid is not None:
            item["record_id"] = rid
        if reason is not None:
            item["reason"] = reason
        result["blockers"].append(item)

    references = protocol.get("requests")
    if type(references) is not dict or set(references) != set(ids):
        block("candidate_request_denominator_mismatch")
        return result
    if (type(protocol.get("max_engine_calls_per_arm")) is not int
            or protocol["max_engine_calls_per_arm"] < len(ids)):
        block("engine_call_cap_below_candidate_count")
    cohorts = {}
    for row in candidates:
        rid = row["record_id"]
        identity = row["chemical_identity"]
        if (row["native_metadata"]["standard_type"] != "Ki"
                or row["target_annotation"]["chembl_target_id"] != "CHEMBL3371"
                or identity is None or row["prediction_issues"]):
            block("candidate_not_human_5ht6_Ki_selector_supported", rid)
            continue
        method = _method_sha256(row)
        if method is None:
            block("candidate_method_not_consistent_Ki", rid)
            continue
        if references[rid] is None:
            block("prepared_request_missing", rid)
            continue
        if row["source_origins"].get("prepared_state_origin") is None:
            block("prepared_source_origin_missing", rid)
            continue
        try:
            request = comparison._bound_json(references[rid])
            receipt = check_source_binding(row, request, inspect_pose_geometry=True)
            charge = receipt["ligand_net_charge_screen"]
            pose = receipt["pose_geometry_status"]
            if charge["rank_eligible"] is not True:
                block("prepared_ligand_net_charge_rank_ineligible", rid, charge["status"])
                continue
            if pose["inside_declared_pocket"] == 0:
                block("prepared_pose_geometry_unusable", rid)
                continue
            if pose["rank_eligible_inside_pocket"] == 0:
                block("prepared_pose_hard_overlap_unusable", rid)
                continue
            inputs = adapter.input_binding(request)
            cohort = {"method_sha256": method, "frame": receipt["cohort"]}
            cohorts[_sha(cohort)] = cohort
            result["requests"][rid] = request
            result["source_inputs"][rid] = inputs
            result["prepared_bindings"][rid] = receipt
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            block("registered_prepared_binding_failed", rid,
                  str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
    if len(identities) < 2:
        block("two_distinct_Ki_chemical_identities_required")
    if len(cohorts) > 1:
        block("method_or_registered_receptor_pocket_frame_mismatch")
    if not result["blockers"]:
        if set(result["prepared_bindings"]) != set(ids) or len(cohorts) != 1:
            block("registered_candidate_binding_incomplete")
        else:
            result["cohort"] = next(iter(cohorts.values()))
    return result


def require_candidates(protocol: dict, source_rows: list[dict]) -> dict:
    result = inspect_candidates(protocol, source_rows)
    if result["blockers"]:
        raise RegisteredAdmissionError(result)
    return result
