"""Validate complete P1 coordinate lineage without importing scientific packages.

This is an admission verifier, not a repair path for incomplete observations.
The caller first verifies the outer journal hash chain and canonical receipt,
then binds the returned evaluator identity to the receipt's evaluator identity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import re

PROFILE = "development_observation_v1"
EVENT_SCHEMA = "betelgeuze.redocking_development_observation/1.0.0"
LINEAGE_SCHEMA = "betelgeuze.development_coordinate_lineage/1.0.0"
COORDINATE_SCHEMA = "betelgeuze.engine_v2_pose_coordinates/1.1.0"
STAGES = ("proposal_generated", "post_v6", "post_v7_optimization", "refinement_selected")
_SHA = re.compile(r"[0-9a-f]{64}")


class LineageValidationError(ValueError):
    """The observed lineage cannot support complete paired admission."""


def _require(condition, message):
    if not condition:
        raise LineageValidationError(message)


def _digest(value, name):
    _require(isinstance(value, str) and _SHA.fullmatch(value), "invalid " + name)
    return value


def _finite(value, name):
    _require(type(value) in (int, float) and math.isfinite(value), "nonfinite/invalid " + name)
    return value


def coordinate_payload_fingerprint(payload):
    """Match identity.coordinate_fingerprint's float64 canonical JSON exactly."""
    _require(isinstance(payload, Mapping) and set(payload) == {"shape", "values_hex"},
             "coordinate payload fields differ")
    shape, values = payload["shape"], payload["values_hex"]
    _require(isinstance(shape, list) and len(shape) == 2
             and all(type(v) is int for v in shape) and shape[0] > 0 and shape[1] == 3,
             "coordinate shape must be positive N by 3")
    _require(isinstance(values, list) and len(values) == shape[0] * 3,
             "coordinate value count differs from shape")
    for text in values:
        _require(isinstance(text, str), "coordinate value is not canonical binary64 hex")
        try:
            value = float.fromhex(text)
        except (ValueError, OverflowError) as exc:
            raise LineageValidationError("invalid coordinate binary64 hex") from exc
        _require(math.isfinite(value) and value.hex() == text,
                 "coordinate value is not finite canonical binary64 hex")
    document = {"schema_id": COORDINATE_SCHEMA, "coordinates": dict(payload)}
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def _events(events, case_id):
    _require(isinstance(events, Sequence) and not isinstance(events, (str, bytes)), "events must be a sequence")
    observed, evaluator, previous_time, active = [], None, -1.0, set()
    for event in events:
        _require(isinstance(event, Mapping), "journal inner event is not an object")
        details = event.get("details", {})
        coordinate_event = event.get("stage") in (*STAGES, "final_ranked") or (
            isinstance(details, Mapping) and "coordinates_binary64" in details)
        p1 = coordinate_event or any(key in event for key in (
            "schema_id", "profile", "sequence", "evaluator_identity", "monotonic_elapsed_seconds"))
        if not p1:
            continue  # P0 supervisor/worker stage event; its outer chain is verified by the caller.
        _require(event.get("schema_id") == EVENT_SCHEMA and event.get("profile") == PROFILE
                 and event.get("case_id") == case_id, "P1 event schema/profile/case differs")
        _require(type(event.get("sequence")) is int and event["sequence"] == len(observed) + 1,
                 "P1 sequence is not contiguous from one")
        identity = _digest(event.get("evaluator_identity"), "evaluator identity")
        evaluator = identity if evaluator is None else evaluator
        _require(identity == evaluator, "P1 evaluator identity changed")
        elapsed = _finite(event.get("elapsed_seconds"), "stage elapsed time")
        clock = _finite(event.get("monotonic_elapsed_seconds"), "monotonic elapsed time")
        _require(elapsed >= 0 and clock >= previous_time, "P1 elapsed time moved backwards")
        previous_time = clock
        stage, phase = event.get("stage"), event.get("phase")
        _require(isinstance(stage, str) and stage and phase in {"start", "complete", "snapshot"},
                 "P1 stage failed or has an invalid phase")
        _require(isinstance(details, Mapping), "P1 details must be an object")
        index = details.get("proposal_index")
        _require(index is None or type(index) is int, "invalid P1 proposal index")
        key = (stage, index)
        if phase == "start":
            _require(key not in active, "duplicate P1 stage start")
            active.add(key)
        elif phase == "complete":
            _require(key in active, "P1 stage completion lacks its start")
            active.remove(key)
        observed.append(event)
    _require(observed and not active, "P1 observation is empty or has unfinished stages")
    return observed, evaluator


def validate_observation_events(events, *, case_id, canonical_row):
    """Bind every complete smoke lineage and ranked pose to a validated receipt."""
    _require(isinstance(canonical_row, Mapping) and canonical_row.get("case_id") == case_id
             and canonical_row.get("engine_id") == "engine_v2" and canonical_row.get("status") == "success",
             "canonical successful Engine V2 case required")
    observed, evaluator = _events(events, case_id)
    candidates = canonical_row["engine_v2_diagnostics"]["candidates"]
    _require(isinstance(candidates, list) and len(candidates) == 64, "canonical candidate denominator differs")
    by_index = {}
    for candidate in candidates:
        index = candidate.get("proposal_index")
        _require(type(index) is int and 0 <= index < 64 and index not in by_index,
                 "canonical candidate indices differ")
        _require(candidate.get("status") == "success", "complete smoke lineage requires 64 successful candidates")
        _finite(candidate.get("score"), "canonical score")
        by_index[index] = candidate
    snapshots = {stage: {} for stage in (*STAGES, "final_ranked")}
    shape = None
    for event in observed:
        details, stage = event["details"], event["stage"]
        if "coordinates_binary64" not in details and stage not in snapshots:
            continue
        _require(stage in snapshots and event["phase"] == "snapshot", "unexpected coordinate lineage stage")
        _require(details.get("schema_id") == LINEAGE_SCHEMA and details.get("coordinate_unit") == "angstrom",
                 "coordinate lineage schema/unit differs")
        index = details.get("proposal_index")
        _require(type(index) is int and 0 <= index < 64 and index not in snapshots[stage],
                 "duplicate or invalid coordinate proposal index")
        payload = details.get("coordinates_binary64")
        digest = coordinate_payload_fingerprint(payload)
        _require(digest == details.get("coordinate_fingerprint_sha256"), "coordinate payload/fingerprint differs")
        shape = payload["shape"] if shape is None else shape
        _require(payload["shape"] == shape, "ligand coordinate shape changed between stages")
        _digest(details.get("proposal_fingerprint_sha256"), "proposal fingerprint")
        _require(isinstance(details.get("candidate_id"), str) and details["candidate_id"], "missing candidate identity")
        snapshots[stage][index] = details
    for stage in STAGES:
        _require(set(snapshots[stage]) == set(range(64)), "coordinate stage is incomplete: " + stage)
    for index, candidate in by_index.items():
        generated = snapshots["proposal_generated"][index]
        selected = snapshots["refinement_selected"][index]
        for stage in ("post_v6", "post_v7_optimization"):
            item = snapshots[stage][index]
            _require(item["proposal_fingerprint_sha256"] == generated["proposal_fingerprint_sha256"]
                     and item["candidate_id"] == generated["candidate_id"], "intermediate lineage parent differs")
        _require(selected.get("parent_proposal_fingerprint_sha256") == generated["proposal_fingerprint_sha256"]
                 and selected["candidate_id"] == generated["candidate_id"], "selected lineage parent differs")
        for key in ("coordinate_fingerprint_sha256", "proposal_fingerprint_sha256", "refinement_receipt_sha256"):
            _digest(candidate.get(key), "canonical " + key)
            _require(selected.get(key) == candidate[key], "selected/canonical " + key + " differs")
        _require(type(selected.get("torsion_selected")) is bool, "selected torsion branch is missing")
        previous = snapshots["post_v7_optimization" if selected["torsion_selected"] else "post_v6"][index]
        _require(previous["coordinate_fingerprint_sha256"] == selected["coordinate_fingerprint_sha256"],
                 "selected coordinates do not match recorded selection branch")
        _require(selected.get("final_penalty_binary64_hex") == candidate.get("refinement_final_penalty_binary64_hex"),
                 "selected/canonical final penalty differs")
    ranked = sorted(candidates, key=lambda c: (float(c["score"]), c["proposal_index"]))[:5]
    final = snapshots["final_ranked"]
    _require(len(final) == 5 and set(final) == {c["proposal_index"] for c in ranked}, "final ranked candidate set differs")
    for key in ("pose_artifact_sha256s", "rmsd_angstroms", "geometric_valid", "chemical_valid"):
        _require(len(canonical_row[key]) == 5, "canonical Top5 denominator differs")
    for rank, candidate in enumerate(ranked, 1):
        index = candidate["proposal_index"]
        item, selected = final[index], snapshots["refinement_selected"][index]
        _require(type(item.get("rank_1based")) is int and item["rank_1based"] == rank, "final rank differs")
        for key in ("coordinate_fingerprint_sha256", "proposal_fingerprint_sha256", "candidate_id"):
            _require(item[key] == selected[key], "final/selected identity differs")
        _require(item.get("evaluated_pose_record_sha256") == candidate["pose_artifact_sha256"]
                 == canonical_row["pose_artifact_sha256s"][rank - 1], "ranked SDF artifact binding differs")
        for candidate_key, row_key in (("rmsd_angstrom", "rmsd_angstroms"),
                                       ("geometric_valid", "geometric_valid"),
                                       ("chemical_valid", "chemical_valid")):
            _require(candidate[candidate_key] == canonical_row[row_key][rank - 1], "ranked evaluation binding differs")
    return {"schema_id": "betelgeuze.redocking_lineage_verification/1.0.0", "status": "verified",
        "case_id": case_id, "profile": PROFILE, "evaluator_identity": evaluator,
        "p1_event_count": len(observed), "coordinate_snapshot_count": 261,
        "complete_stage_candidate_counts": {stage: len(snapshots[stage]) for stage in STAGES},
        "canonical_candidate_bindings": 64, "top5_bindings": 5, "coordinate_shape": shape,
        "coordinate_fingerprint_policy": COORDINATE_SCHEMA}
