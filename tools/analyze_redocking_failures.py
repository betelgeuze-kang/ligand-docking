"""Diagnose retained development docking failures without molecular execution.

The CLI reads a hash-pinned P0/P1 delivery and optional hash-pinned PoseBusters
replay artifacts.  It preserves the fixed 32-case denominator, independently
classifies candidate pools, and relates the recorded score/refinement terms to
the recorded outcomes.  It never changes a score, rank, pose, or success rule.
All imports are from the Python standard library.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import struct
from typing import Any
import zipfile


SOURCE_RUN = 41697499611
SOURCE_COMMIT = "16980a83cd425994bdb596077785ebe3a96542a6"
SOURCE_TREE = "fa82392f58eaf47f347ce04ca1b1a0ae9b3b35cd"
DELIVERY_SHA256 = "a0bfae8c26637050a6623261729d6cefa16a3a9e4de33bcd975fc79690b3d005"
REPLAY_COMMIT = "bcee827ae3342ccc19f8e389a400e0c3ca282ad4"
REPLAY_RUN = 41778486589
RMSD_THRESHOLD = 2.0
TOP_K = (1, 3, 5)
SCORE_COMPONENTS = (
    "typed_vdw", "electrostatics", "directional_hbond", "hydrophobic_contact",
    "desolvation_proxy", "torsion_energy", "ligand_strain", "weak_pocket_prior",
)
CHEMICAL_CHECKS = (
    "sanitization", "inchi_convertible", "all_atoms_connected", "molecular_formula",
    "molecular_bonds", "double_bond_stereochemistry", "tetrahedral_chirality",
    "bond_lengths", "bond_angles", "internal_steric_clash", "aromatic_ring_flatness",
    "double_bond_flatness", "internal_energy",
)
GEOMETRIC_CHECKS = (
    "protein-ligand_maximum_distance", "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors", "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters", "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors", "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)
CHECKS = CHEMICAL_CHECKS + GEOMETRIC_CHECKS
CATEGORIES = (
    "preparation_failure", "incomplete_observation", "no_near_native",
    "near_native_only_invalid", "valid_near_native_ranked_out",
    "valid_near_native_recovered",
)
COORDINATE_STAGES = (
    "proposal_generated", "post_v6", "post_v7_optimization", "refinement_selected",
)
FOCUS_ARTIFACTS = {
    "6T88_MWQ": ("13298852984", "7870811bcf6e454af51b103901346e678c5e4bf4baeee34de09c3e88bd368688"),
    "6YSP_PAL": ("13299920717", "7e9b86eef9cee6d5daea63f28cc41106ccc8deef7f8649f01413b417ac9b63e2"),
}
NUMERIC_FOCUS_COLUMNS = (
    "rmsd", "kabsch_rmsd", "centroid_distance", "smallest_distance_protein",
    "most_extreme_relative_distance_protein", "num_pairwise_clashes_protein",
    "volume_overlap_protein", "energy_ratio", "ensemble_avg_energy", "mol_pred_energy",
    "number_clashes", "shortest_noncovalent_relative_distance",
)


class DiagnosisError(ValueError):
    """The supplied evidence cannot support the requested diagnosis."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosisError(message)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return sha256(canonical(value))


def parse_json(payload: bytes, label: str = "JSON") -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result

    def reject(value):
        raise DiagnosisError(f"{label}: nonfinite JSON value {value}")

    try:
        return json.loads(payload, object_pairs_hook=unique, parse_constant=reject)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiagnosisError(f"{label}: invalid JSON") from exc


def finite(value: Any, label: str, *, minimum: float | None = None) -> float:
    require(type(value) in (float, int) and math.isfinite(value), f"{label}: nonfinite or nonnumeric")
    require(minimum is None or value >= minimum, f"{label}: below allowed minimum")
    return float(value)


def binary64(text: Any, label: str = "binary64") -> float:
    require(type(text) is str, f"{label}: canonical hexadecimal string required")
    try:
        value = float.fromhex(text)
    except (ValueError, OverflowError) as exc:
        raise DiagnosisError(f"{label}: invalid binary64") from exc
    require(math.isfinite(value) and value.hex() == text, f"{label}: nonfinite/noncanonical binary64")
    return value


def self_hash(document: dict, key: str, label: str) -> str:
    observed = document.get(key)
    require(type(observed) is str and re.fullmatch(r"[0-9a-f]{64}", observed) is not None,
            f"{label}: missing self hash")
    require(digest({k: v for k, v in document.items() if k != key}) == observed,
            f"{label}: self hash mismatch")
    return observed


def safe_member(name: str) -> str:
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and p.as_posix() == name and
            all(part not in ("", ".", "..") for part in p.parts) and "\\" not in name,
            "unsafe or noncanonical archive member")
    return name


@contextmanager
def opened_zip(payload: bytes, label: str, *, max_members: int = 25000):
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            require(len(entries) <= max_members and len({e.filename for e in entries}) == len(entries),
                    f"{label}: excessive or duplicate archive entries")
            require(sum(e.file_size for e in entries) <= 400 * 1024 * 1024,
                    f"{label}: expanded archive exceeds bound")
            for entry in entries:
                safe_member(entry.filename)
                require(not entry.is_dir() and not entry.flag_bits & 1 and
                        (entry.external_attr >> 16) & 0o170000 != 0o120000,
                        f"{label}: directory, encryption, or symbolic link entry")
            yield archive
    except zipfile.BadZipFile as exc:
        raise DiagnosisError(f"{label}: invalid ZIP") from exc


def verify_inventory(archive, *, name: str, key: str, size_key: str) -> tuple[dict, dict]:
    inventory = parse_json(archive.read(name), name)
    entries = inventory.get(key)
    require(type(entries) is list, "inventory entries missing")
    by_name = {}
    total = 0
    for entry in entries:
        path = safe_member(entry["path"])
        require(path not in by_name and path != name, "duplicate/self-referential inventory entry")
        payload = archive.read(path)
        require(type(entry[size_key]) is int and len(payload) == entry[size_key] and
                sha256(payload) == entry["sha256"], f"inventory payload mismatch: {path}")
        by_name[path] = entry
        total += len(payload)
    require(set(by_name) | {name} == set(archive.namelist()), "inventory does not cover exact archive membership")
    if name == "artifact-inventory.json":
        require(inventory.get("schema_id") == "betelgeuze.redocking_artifact_inventory/1.0.0" and
                inventory.get("payload_file_count") == len(by_name) and
                inventory.get("archive_member_count") == len(by_name) + 1 and
                inventory.get("bytes") == total and inventory.get("excluded_paths") == [],
                "sealed inventory counts/schema differ")
    return inventory, by_name


def canonical_coordinate_fingerprint(payload: dict) -> str:
    require(type(payload) is dict and set(payload) == {"shape", "values_hex"}, "invalid coordinate payload")
    shape, values = payload["shape"], payload["values_hex"]
    require(type(shape) is list and len(shape) == 2 and type(shape[0]) is int and
            0 < shape[0] <= 10000 and type(shape[1]) is int and shape[1] == 3 and
            type(values) is list and len(values) == 3 * shape[0], "invalid coordinate dimensions")
    for value in values:
        binary64(value, "coordinate")
    return digest({"schema_id": "betelgeuze.engine_v2_pose_coordinates/1.1.0", "coordinates": payload})


def verify_journal(archive, prefix: str, request: dict, request_sha: str,
                   receipt: dict, row: dict) -> tuple[list[dict], dict]:
    identity = parse_json(archive.read(prefix + "identity.json"))
    ident_sha = digest(identity)
    require(identity.get("case_id") == row["case_id"] and identity.get("task") == row["engine_id"] and
            identity.get("source") == request["source"] and identity.get("request_sha256") == request_sha,
            "journal/request identity mismatch")
    checkpoint = parse_json(archive.read(prefix + "checkpoint.json"))
    count = checkpoint.get("last_sequence")
    require(type(count) is int and 1 <= count <= 10000, "invalid journal event count")
    names = [prefix + f"event-{i:06d}.json" for i in range(1, count + 1)]
    require(sorted(n for n in archive.namelist() if n.startswith(prefix + "event-")) == names,
            "journal event sequence gap or extra event")
    previous, total, events = None, 0, []
    for i, name in enumerate(names, 1):
        payload = archive.read(name)
        envelope = parse_json(payload, name)
        require(envelope.get("schema_id") == "betelgeuze.redocking_phase_journal_event/1.0.0" and
                type(envelope.get("journal_sequence")) is int and envelope["journal_sequence"] == i and
                envelope.get("identity_sha256") == ident_sha and
                envelope.get("previous_event_sha256") == previous, "journal hash-chain identity mismatch")
        previous = self_hash(envelope, "event_sha256", name)
        require(type(envelope.get("event")) is dict, "journal event is not an object")
        events.append(envelope["event"])
        total += len(payload)
    require(checkpoint.get("schema_id") == "betelgeuze.redocking_phase_checkpoint/1.0.0" and
            checkpoint.get("identity_sha256") == ident_sha and checkpoint.get("event_sha256") == previous and
            checkpoint.get("event_path") == PurePosixPath(names[-1]).name and
            checkpoint.get("event_bytes_total") == total and checkpoint.get("last_event") == events[-1],
            "journal checkpoint mismatch")
    last = events[-1]
    require(last.get("stage") == "worker" and last.get("phase") == "complete" and
            last.get("details", {}).get("receipt_sha256") == receipt["receipt_sha256"] and
            last["details"].get("scientific_status") == row["status"] and
            last["details"].get("status") == "completed", "journal scientific completion mismatch")
    return events, {"identity_sha256": ident_sha, "event_count": count,
                    "last_event_sha256": previous, "event_bytes": total}


def historical_score_sum(terms: dict) -> float:
    """Match the original Python 3.10 ordered float sum, also on Python 3.12+."""
    require(set(terms) == set(SCORE_COMPONENTS) | {"total_score"}, "score component set changed")
    total = 0.0
    for name in SCORE_COMPONENTS:
        total += binary64(terms[name], name)
    require(total.hex() == terms["total_score"], "recorded component sum differs from total score")
    return total


def validate_candidate(candidate: dict) -> None:
    require(type(candidate) is dict and type(candidate.get("proposal_index")) is int and
            candidate["proposal_index"] >= 0, "invalid proposal index")
    status = candidate.get("status")
    require(status in ("success", "failure"), "invalid candidate status")
    if status == "failure":
        require(type(candidate.get("error_code")) is str and bool(candidate["error_code"]),
                "untyped candidate failure")
        return
    finite(candidate.get("score"), "candidate score")
    finite(candidate.get("rmsd_angstrom"), "candidate RMSD", minimum=0)
    require(type(candidate.get("chemical_valid")) is bool and type(candidate.get("geometric_valid")) is bool,
            "validity is not an evaluated boolean")
    failed = candidate.get("posebusters_failed_check_ids")
    require(type(failed) is list and failed == [name for name in CHECKS if name in failed],
            "failed-check IDs are unknown, duplicated, or out of order")
    require(candidate["chemical_valid"] == (not bool(set(failed) & set(CHEMICAL_CHECKS))) and
            candidate["geometric_valid"] == (not bool(set(failed) & set(GEOMETRIC_CHECKS))),
            "validity does not match its failed-check IDs")


def classify_pool(candidates: list[dict] | None, *, preparation_status: str,
                  candidate_budget: int, top_k: int) -> dict:
    """Return one exclusive category and separate overlapping scientific flags."""
    require(type(top_k) is int and top_k > 0 and type(candidate_budget) is int and candidate_budget > 0,
            "invalid candidate budget or Top-k")
    require(preparation_status in ("success", "failure", "unobserved"), "invalid preparation status")
    if preparation_status == "unobserved" or candidates is None:
        require(preparation_status != "failure", "a measured preparation failure needs an empty candidate list")
        return {"category": "incomplete_observation", "pool_complete": False,
                "known_near_native_count": None, "known_valid_near_native_count": None,
                "best_valid_near_native_rank": None, "known_topk_recovered": None}
    require(type(candidates) is list, "candidate array required")
    if preparation_status == "failure":
        require(candidates == [], "preparation failure contains fabricated candidates")
        return {"category": "preparation_failure", "pool_complete": True,
                "known_near_native_count": 0, "known_valid_near_native_count": 0,
                "best_valid_near_native_rank": None, "known_topk_recovered": False}
    for candidate in candidates:
        validate_candidate(candidate)
    indices = [candidate["proposal_index"] for candidate in candidates]
    require(len(indices) == len(set(indices)) and all(i < candidate_budget for i in indices),
            "duplicate or out-of-budget proposal index")
    ranked = sorted((c for c in candidates if c["status"] == "success"),
                    key=lambda c: (float(c["score"]), c["proposal_index"]))
    near = [(rank, c) for rank, c in enumerate(ranked, 1) if c["rmsd_angstrom"] <= RMSD_THRESHOLD]
    valid_near = [(rank, c) for rank, c in near if c["chemical_valid"] and c["geometric_valid"]]
    complete = len(ranked) == candidate_budget and set(indices) == set(range(candidate_budget))
    best_rank = valid_near[0][0] if valid_near else None
    recovered = best_rank is not None and best_rank <= top_k
    if not complete:
        category = "incomplete_observation"
    elif not near:
        category = "no_near_native"
    elif not valid_near:
        category = "near_native_only_invalid"
    elif not recovered:
        category = "valid_near_native_ranked_out"
    else:
        category = "valid_near_native_recovered"
    return {"category": category, "pool_complete": complete,
            "known_near_native_count": len(near), "known_valid_near_native_count": len(valid_near),
            "known_invalid_near_native_count": len(near) - len(valid_near),
            "has_any_invalid_near_native": len(near) > len(valid_near),
            "has_any_valid_near_native": bool(valid_near),
            "best_valid_near_native_rank": best_rank, "known_topk_recovered": recovered}


def distribution(values: list[float]) -> dict:
    present = [float(x) for x in values if math.isfinite(x)]
    return {"observed": len(present), "missing_or_nonfinite": len(values) - len(present),
            "minimum": min(present) if present else None,
            "median": statistics.median(present) if present else None,
            "maximum": max(present) if present else None}


def rank_values(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    first = 0
    while first < len(order):
        end = first + 1
        while end < len(order) and values[order[end]] == values[order[first]]:
            end += 1
        for index in order[first:end]:
            ranks[index] = (first + 1 + end) / 2
        first = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float | None:
    require(len(left) == len(right), "correlation arrays differ in length")
    if len(left) < 2:
        return None
    a, b = rank_values(left), rank_values(right)
    ma, mb = statistics.mean(a), statistics.mean(b)
    xx = math.fsum((x-ma)**2 for x in a)
    yy = math.fsum((y-mb)**2 for y in b)
    return math.fsum((x-ma)*(y-mb) for x, y in zip(a, b)) / math.sqrt(xx*yy) if xx and yy else None


def bind_lineage(events: list[dict], row: dict, evaluator: str) -> tuple[dict, dict]:
    candidates = row["engine_v2_diagnostics"]["candidates"]
    require([c.get("proposal_index") for c in candidates] == list(range(64)), "complete proposal order changed")
    p1 = [event for event in events if "schema_id" in event]
    require(p1 and all(event.get("schema_id") == "betelgeuze.redocking_development_observation/1.0.0" and
                      event.get("profile") == "development_observation_v1" and
                      event.get("case_id") == row["case_id"] and event.get("evaluator_identity") == evaluator and
                      event.get("sequence") == i for i, event in enumerate(p1, 1)), "P1 identity or sequence differs")
    stages = {name: {} for name in COORDINATE_STAGES + ("final_ranked",)}
    for event in p1:
        if event["stage"] not in stages:
            continue
        details = event["details"]
        index = details.get("proposal_index")
        require(event["phase"] == "snapshot" and type(index) is int and index not in stages[event["stage"]],
                "duplicate/invalid coordinate snapshot")
        require(details.get("schema_id") == "betelgeuze.development_coordinate_lineage/1.0.0" and
                details.get("coordinate_unit") == "angstrom" and
                canonical_coordinate_fingerprint(details["coordinates_binary64"]) == details["coordinate_fingerprint_sha256"],
                "coordinate snapshot fingerprint differs")
        stages[event["stage"]][index] = details
    for stage in COORDINATE_STAGES:
        require(set(stages[stage]) == set(range(64)), f"coordinate lineage incomplete: {stage}")
    scored = [e["details"] for e in p1 if e["stage"] == "scored_candidates" and e["phase"] == "snapshot"]
    require(len(scored) == 1 and scored[0].get("benchmark_rank_rule") == "finite_success_score_then_proposal_index" and
            scored[0].get("candidate_count") == 64 and len(scored[0].get("candidates", [])) == 64,
            "scoring snapshot/rank rule differs")
    score_rows = {c["proposal_index"]: c for c in scored[0]["candidates"]}
    require(set(score_rows) == set(range(64)), "score snapshot index set differs")
    torsion = Counter()
    candidate_lineage = {}
    for candidate in candidates:
        validate_candidate(candidate)
        index = candidate["proposal_index"]
        generated = stages["proposal_generated"][index]
        post_v6 = stages["post_v6"][index]
        optimized = stages["post_v7_optimization"][index]
        selected = stages["refinement_selected"][index]
        require(selected.get("parent_proposal_fingerprint_sha256") == generated["proposal_fingerprint_sha256"] and
                all(stages[s][index]["candidate_id"] == generated["candidate_id"] for s in COORDINATE_STAGES),
                "lineage parent/candidate identity differs")
        require(type(selected.get("torsion_selected")) is bool and type(optimized.get("torsion_evaluated")) is bool,
                "torsion decision not observed")
        parent = optimized if selected["torsion_selected"] else post_v6
        for field in ("coordinate_fingerprint_sha256", "proposal_fingerprint_sha256", "refinement_receipt_sha256"):
            require(selected.get(field) == candidate[field], "selected candidate binding differs")
        require(selected["coordinate_fingerprint_sha256"] == parent["coordinate_fingerprint_sha256"] and
                selected["final_penalty_binary64_hex"] == candidate["refinement_final_penalty_binary64_hex"],
                "selected branch/final penalty differs")
        score = score_rows[index]
        terms = score["score_terms"]
        require(self_hash(terms, "receipt_sha256", "score terms") == candidate["score_terms_receipt_sha256"] and
                terms["proposal_fingerprint_sha256"] == candidate["proposal_fingerprint_sha256"] and
                score["coordinate_fingerprint_sha256"] == candidate["coordinate_fingerprint_sha256"] and
                score["score_binary64_hex"] == float(candidate["score"]).hex() and
                score["selection_eligible"] is candidate["selection_eligible"], "score receipt/candidate binding differs")
        recorded = candidate["score_term_binary64_hex"]
        require(all(terms[name + "_binary64_hex"] == recorded[name]
                    for name in SCORE_COMPONENTS + ("total_score",)), "score-term projection differs")
        require(historical_score_sum(recorded).hex() == float(candidate["score"]).hex(), "candidate score changed")
        trials = optimized.get("torsion_trial_evaluation_count")
        require(type(trials) is int and trials >= 0 and
                (optimized["torsion_evaluated"] or trials == 0), "torsion trial count is invalid")
        reason = optimized.get("torsion_evaluation_skip_reason")
        require(type(reason) is str and bool(reason), "torsion skip reason absent")
        torsion["observed_candidates"] += 1
        torsion["evaluated_candidates"] += optimized["torsion_evaluated"]
        torsion["selected_candidates"] += selected["torsion_selected"]
        torsion["trial_evaluations"] += trials
        torsion["skip_reason:" + reason] += 1
        for field in ("objective_id", "objective_semantics", "objective_unit"):
            require(selected.get(field) == optimized.get(field), "objective metadata differs")
        require(selected["objective_id"] == "v7_receptor_plus_internal_quartic_overlap" and
                selected["objective_semantics"] == "geometric_overlap_proxy_not_physical_energy" and
                selected["objective_unit"] == "angstrom^4", "unexpected refinement objective")
        candidate_lineage[index] = {
            "torsion_evaluated": optimized["torsion_evaluated"], "torsion_selected": selected["torsion_selected"],
            "torsion_trial_evaluation_count": trials, "torsion_evaluation_skip_reason": reason,
            "selection_reason": selected.get("selection_reason"),
            "v6_to_v7_coordinates_changed": post_v6["coordinate_fingerprint_sha256"] != optimized["coordinate_fingerprint_sha256"],
            "v6_to_selected_coordinates_changed": post_v6["coordinate_fingerprint_sha256"] != selected["coordinate_fingerprint_sha256"],
            "optimized_receptor_penalty_binary64_hex": optimized["receptor_penalty_binary64_hex"],
            "optimized_internal_penalty_binary64_hex": optimized["internal_penalty_binary64_hex"],
            "optimized_combined_penalty_binary64_hex": optimized["combined_penalty_binary64_hex"],
        }
    ranked = sorted(candidates, key=lambda c: (c["score"], c["proposal_index"]))
    finals = stages["final_ranked"]
    require(len(finals) == 5 and set(finals) == {c["proposal_index"] for c in ranked[:5]}, "Top5 index set differs")
    for rank, candidate in enumerate(ranked[:5], 1):
        final = finals[candidate["proposal_index"]]
        require(final.get("rank_1based") == rank and
                final.get("evaluated_pose_record_sha256") == candidate["pose_artifact_sha256"] == row["pose_artifact_sha256s"][rank-1],
                "Top5 record/rank binding differs")
        require(float(row["rmsd_angstroms"][rank-1]).hex() == float(candidate["rmsd_angstrom"]).hex() and
                row["chemical_valid"][rank-1] is candidate["chemical_valid"] and
                row["geometric_valid"][rank-1] is candidate["geometric_valid"], "Top5 evaluation binding differs")
    lookups = [e["details"] for e in p1 if e["stage"] == "evaluation_cache_lookup" and e["phase"] == "snapshot"]
    require(len(lookups) == 2 and [l["record_count"] for l in lookups] == [64, 5] and
            [l["record_sha256s"] for l in lookups] == [[c["pose_artifact_sha256"] for c in ranked],
                                                     [c["pose_artifact_sha256"] for c in ranked[:5]]],
            "evaluation record sequence differs")
    return {"coordinate_snapshot_count": 261, "score_receipts_verified": 64,
            "historical_ordered_score_sums_exact": 64, "torsion": dict(torsion)}, candidate_lineage


def topk_metrics(row: dict | None) -> dict:
    if row is None:
        return {f"{prefix}{k}": None for prefix in ("top", "valid_top") for k in TOP_K}
    require(row.get("status") in ("success", "failure"), "unknown scientific row status")
    keys = ("rmsd_angstroms", "chemical_valid", "geometric_valid", "pose_artifact_sha256s")
    if row["status"] == "failure":
        require(bool(row.get("failure_code")) and all(row.get(key) == [] for key in keys), "untyped/incomplete failure row")
        return {f"{prefix}{k}": 0 for prefix in ("top", "valid_top") for k in TOP_K}
    require(all(type(row.get(key)) is list and len(row[key]) == 5 for key in keys), "successful Top5 row is incomplete")
    near = [finite(x, "Top5 RMSD", minimum=0) <= RMSD_THRESHOLD for x in row["rmsd_angstroms"]]
    require(all(type(x) is bool for key in ("chemical_valid", "geometric_valid") for x in row[key]), "Top5 validity not boolean")
    valid = [n and c and g for n, c, g in zip(near, row["chemical_valid"], row["geometric_valid"])]
    return {**{f"top{k}": int(any(near[:k])) for k in TOP_K},
            **{f"valid_top{k}": int(any(valid[:k])) for k in TOP_K}}


def analyze_case(row: dict, *, global_index: int, bindings: dict,
                 lineage: dict, candidate_lineage: dict) -> dict:
    diagnostic = row["engine_v2_diagnostics"]
    candidates = diagnostic["candidates"]
    budget = diagnostic["candidate_budget"]
    require(budget == 64, "candidate budget changed")
    classifications = {f"top{k}": classify_pool(candidates, preparation_status=diagnostic["preparation_status"],
                                                candidate_budget=budget, top_k=k) for k in TOP_K}
    recoveries = topk_metrics(row)
    if row["status"] == "failure":
        require(diagnostic["preparation_status"] == "failure" and candidates == [],
                "unexpected non-preparation case failure in this frozen run")
        return {"case_id": row["case_id"], "global_index": global_index, "status": "failure",
                "preparation_failure_code": diagnostic["preparation_failure_code"], "classifications": classifications,
                "recoveries": recoveries, "candidate_count": 0, "candidates": [], "bindings": bindings,
                "lineage": lineage}
    require(diagnostic["candidate_success_count"] == len(candidates) == 64 and diagnostic["candidate_failure_count"] == 0,
            "successful frozen case lacks its complete candidate pool")
    ranked = sorted(candidates, key=lambda c: (c["score"], c["proposal_index"]))
    normalized = []
    for rank, candidate in enumerate(ranked, 1):
        initial = binary64(candidate["refinement_initial_penalty_binary64_hex"])
        final = binary64(candidate["refinement_final_penalty_binary64_hex"])
        normalized.append({
            **{key: candidate[key] for key in (
                "proposal_index", "proposal_mode", "status", "score", "rmsd_angstrom", "chemical_valid",
                "geometric_valid", "posebusters_failed_check_ids", "selection_eligible", "pose_artifact_sha256",
                "coordinate_fingerprint_sha256", "proposal_fingerprint_sha256", "refinement_receipt_sha256",
                "score_terms_receipt_sha256", "score_term_binary64_hex", "refinement_initial_penalty_binary64_hex",
                "refinement_final_penalty_binary64_hex", "refinement_accepted_steps", "refinement_accepted_rotation_steps",
            )},
            "score_rank": rank, "near_native": candidate["rmsd_angstrom"] <= RMSD_THRESHOLD,
            "joint_valid": candidate["chemical_valid"] and candidate["geometric_valid"],
            "refinement_penalty_direction": "decreased" if final < initial else "increased" if final > initial else "unchanged",
            "lineage": candidate_lineage[candidate["proposal_index"]],
        })
    near = [c for c in normalized if c["near_native"]]
    valid_near = [c for c in near if c["joint_valid"]]
    for k in TOP_K:
        require(recoveries[f"valid_top{k}"] == int(classifications[f"top{k}"]["known_topk_recovered"]),
                "published Top-k differs from independently ranked candidate pool")
    comparison = None
    if valid_near:
        target, first = valid_near[0], normalized[0]
        comparison = {"score_top1_proposal_index": first["proposal_index"],
                      "best_scored_valid_near_native_proposal_index": target["proposal_index"],
                      "best_scored_valid_near_native_rank": target["score_rank"],
                      "score_difference_valid_near_minus_top1": target["score"] - first["score"],
                      "weighted_component_differences_valid_near_minus_top1": {
                          key: binary64(target["score_term_binary64_hex"][key]) - binary64(first["score_term_binary64_hex"][key])
                          for key in SCORE_COMPONENTS}}
    return {"case_id": row["case_id"], "global_index": global_index, "status": "success",
            "preparation_failure_code": "", "candidate_count": 64, "classifications": classifications,
            "recoveries": recoveries, "bindings": bindings, "lineage": lineage, "candidates": normalized,
            "candidate_failed_check_counts": dict(sorted(Counter(check for c in candidates for check in c["posebusters_failed_check_ids"]).items())),
            "minimum_rmsd_angstrom": min(c["rmsd_angstrom"] for c in candidates),
            "minimum_valid_rmsd_angstrom": min((c["rmsd_angstrom"] for c in normalized if c["joint_valid"]), default=None),
            "near_native_candidate_ranks": [c["score_rank"] for c in near],
            "valid_near_native_candidate_ranks": [c["score_rank"] for c in valid_near],
            "valid_near_native_score_contrast": comparison,
            "within_case_score_rmsd_spearman": spearman([c["score"] for c in candidates], [c["rmsd_angstrom"] for c in candidates])}


def read_frozen_delivery(path: Path, *, expected_sha256: str = DELIVERY_SHA256) -> tuple[list[dict], dict, dict]:
    payload = path.read_bytes()
    require(sha256(payload) == expected_sha256 == DELIVERY_SHA256, "frozen delivery SHA256 mismatch")
    cases, engine_rows, archive_proofs = [], {engine: [] for engine in ("engine_v2", "vina", "gnina")}, []
    expected_ids = None
    with opened_zip(payload, "delivery", max_members=200) as delivery:
        top_inventory, _ = verify_inventory(delivery, name="delivery-inventory.json", key="payload_files", size_key="size_bytes")
        require(top_inventory["execution_run_id"] == SOURCE_RUN and top_inventory["execution_commit"] == SOURCE_COMMIT,
                "delivery source identity differs")
        aggregate = parse_json(delivery.read(f"run-{SOURCE_RUN}/original-combined/analysis.json"))
        require(aggregate["analysis_scope"] == "contaminated_development" and aggregate["claim_safe"] is False and
                aggregate["attempted_development_cases"] == 32, "unexpected aggregate scope")
        aggregate_cases = {c["case_id"]: c for c in aggregate["cases"]}
        for start in (2, 10, 18, 26):
            key = f"development-{start}"
            raw = delivery.read(f"run-{SOURCE_RUN}/{key}-artifact.zip")
            previous = parse_json(delivery.read(f"run-{SOURCE_RUN}/{key}-archive-verification.json"))
            require(sha256(raw) == previous["outer_sha256_verified"] and len(raw) == previous["github_artifact"]["size_in_bytes"],
                    "original Actions artifact digest/size differs")
            with opened_zip(raw, key, max_members=1) as actions:
                require(actions.namelist() == ["sealed-evidence.zip"], "unexpected Actions artifact contents")
                sealed = actions.read("sealed-evidence.zip")
            require(sha256(sealed) == previous["inner_sha256"], "sealed archive SHA256 mismatch")
            with opened_zip(sealed, key + "/sealed") as archive:
                inv, names = verify_inventory(archive, name="artifact-inventory.json", key="files", size_key="size")
                require(sha256(archive.read("artifact-inventory.json")) == previous["sealed_archive_verification"]["inventory_sha256"],
                        "sealed inventory SHA256 mismatch")
                manifest = parse_json(archive.read("development/run-manifest.json"))
                source = manifest["source"]
                require(source["commit"] == SOURCE_COMMIT and source["tree"] == SOURCE_TREE and
                        source["workflow_run_id"] == str(SOURCE_RUN) and source["workflow_run_attempt"] == "1" and
                        manifest["candidate_count"] == 64 and manifest["output_pose_count"] == 5 and
                        manifest["rmsd_threshold_angstrom"] == RMSD_THRESHOLD and
                        manifest["active_indices"] == list(range(start, start+8)) and
                        manifest["development_indices"] == list(range(2, 34)), "development manifest differs")
                ids = [manifest["case_ids"][i] for i in manifest["development_indices"]]
                require(expected_ids is None or ids == expected_ids, "cohort changed between shards")
                expected_ids = ids
                for index in manifest["active_indices"]:
                    case = parse_json(archive.read(f"development/case-{index:02d}.json"))
                    cid = manifest["case_ids"][index]
                    require(case["case_id"] == cid and case["global_index"] == index and
                            case["seed"] == manifest["seed_base"] + index, "case index/seed binding differs")
                    require(cid in aggregate_cases and set(case["engines"]) == set(aggregate_cases[cid]["engines"]),
                            "original aggregate has different engine coverage")
                    # Aggregation adds observation summaries and omits worker paths.
                    # Bind its scientific row and shared execution evidence explicitly.
                    for engine, item in case["engines"].items():
                        combined = aggregate_cases[cid]["engines"][engine]
                        require(all(item[field] == combined[field] for field in (
                            "row", "receipt_sha256", "execution", "errors", "observation_status", "operation_status")),
                            "original aggregate differs from raw scientific or execution evidence")
                    case_root = f"development/cases/{cid}"
                    materialization = parse_json(archive.read(case_root + "/materialization/materialization.json"))
                    materialization_sha = self_hash(materialization, "receipt_sha256", "materialization")
                    require(materialization["case_id"] == cid and materialization["frozen_case_seed"] == case["seed"], "materialization identity differs")
                    materialized_inputs = {}
                    for role, suffix in (("seed", "ligand_start_conf.sdf"), ("native", "ligand.sdf"),
                                         ("reference", "ligands.sdf"), ("receptor", "protein.pdb")):
                        input_path = f"{case_root}/materialization/inputs/{cid}/{cid}_{suffix}"
                        materialized_inputs[role] = names[input_path]["sha256"]
                        require(materialized_inputs[role] == materialization["artifact_sha256s"][suffix],
                                "materialization file content differs from its receipt")
                    for engine, item in case["engines"].items():
                        require(engine in engine_rows and item["observation_status"] == "observed" and
                                item["operation_status"] == "completed", "unobserved/incomplete frozen engine row")
                        prefix = case_root + f"/engines/{engine}/"
                        request_path, receipt_path = prefix + "request.json", prefix + "receipt.json"
                        request = parse_json(archive.read(request_path))
                        receipt = parse_json(archive.read(receipt_path))
                        receipt_sha = self_hash(receipt, "receipt_sha256", receipt_path)
                        row = receipt["result"]
                        require(row == item["row"] and row["case_id"] == cid and row["engine_id"] == engine and
                                receipt_sha == item["receipt_sha256"] and names[request_path]["sha256"] == item["request_sha256"] and
                                request["source"] == source and request["case_id"] == cid and request["global_index"] == index and
                                request["task"] == engine and receipt["materialization_receipt_sha256"] == materialization_sha and
                                receipt["fresh_execution"] is True and receipt["cache_read_allowed"] is False,
                                "request/receipt/materialization binding differs")
                        require(receipt["input_sha256s"] == materialized_inputs == {
                            role: row[role + "_artifact_sha256"] for role in ("seed", "native", "reference", "receptor")},
                                "receipt input identity differs")
                        execution = item["execution"]
                        self_hash(execution, "control_sha256", "process execution")
                        require(execution["returncode"] == 0 and execution["termination"] == "exited" and execution["cleanup_complete"] is True,
                                "worker did not complete")
                        engine_rows[engine].append({"case_id": cid, "status": row["status"],
                                                    "failure_code": row["failure_code"], "recoveries": topk_metrics(row)})
                        if engine != "engine_v2":
                            continue
                        events, journal = verify_journal(archive, prefix + "journal/", request, names[request_path]["sha256"], receipt, row)
                        bindings = {"artifact_key": key, "artifact_id": previous["github_artifact"]["id"],
                                    "case_root": case_root, "seed": case["seed"], "receipt_sha256": receipt_sha,
                                    "receipt_file_sha256": names[receipt_path]["sha256"], "request_file_sha256": names[request_path]["sha256"],
                                    "input_sha256s": receipt["input_sha256s"], "evaluation_pipeline_sha256": receipt["evaluation_pipeline_sha256"],
                                    "journal": journal}
                        lineage, by_candidate = (bind_lineage(events, row, receipt["evaluation_pipeline_sha256"])
                                                 if row["status"] == "success" else ({"coordinate_snapshot_count": 0, "score_receipts_verified": 0}, {}))
                        cases.append(analyze_case(row, global_index=index, bindings=bindings, lineage=lineage, candidate_lineage=by_candidate))
                archive_proofs.append({"key": key, "artifact_id": previous["github_artifact"]["id"],
                                       "outer_sha256": sha256(raw), "sealed_sha256": sha256(sealed),
                                       "verified_payload_files": len(names), "verified_payload_bytes": inv["bytes"],
                                       "inventory_sha256": sha256(archive.read("artifact-inventory.json"))})
    require(expected_ids is not None and [c["case_id"] for c in cases] == expected_ids and len(cases) == 32,
            "fixed development cohort is incomplete or reordered")
    require(all(len(rows) == 32 for rows in engine_rows.values()), "fixed engine denominator changed")
    return cases, engine_rows, {"delivery_path": str(path.resolve()), "delivery_sha256": sha256(payload),
                               "source_run_id": SOURCE_RUN, "source_commit": SOURCE_COMMIT, "source_tree": SOURCE_TREE,
                               "archives": archive_proofs, "historical_aggregate_metrics": aggregate["metrics"]}


def typed_value(cell: dict) -> Any:
    kind = cell.get("type")
    if "binary64_be" in cell:
        try:
            value = struct.unpack(">d", bytes.fromhex(cell["binary64_be"]))[0]
        except (ValueError, struct.error) as exc:
            raise DiagnosisError("invalid fullReport binary64 bits") from exc
        require(kind in ("numpy.float64", "builtins.float") and cell.get("hex") == value.hex(),
                "fullReport float type/hex differs from bits")
        require(cell.get("missing") == ("NaN" if math.isnan(value) else None), "fullReport float missingness differs")
        return value
    if kind in ("numpy.bool_", "builtins.bool"):
        require(type(cell.get("value")) is bool, "fullReport boolean was coerced")
        return cell["value"]
    if kind in ("numpy.int64", "builtins.int"):
        try:
            value = int(cell["decimal"])
        except (KeyError, ValueError) as exc:
            raise DiagnosisError("fullReport integer is invalid") from exc
        require(str(value) == cell["decimal"], "noncanonical fullReport integer")
        return value
    if kind in ("numpy.str_", "builtins.str"):
        require(type(cell.get("value")) is str, "fullReport string is invalid")
        return cell["value"]
    if kind in ("pandas.NA", "builtins.NoneType"):
        return None
    raise DiagnosisError(f"unsupported fullReport scalar type {kind}")


def read_focus_replays(root: Path, cases: list[dict]) -> dict:
    by_id = {c["case_id"]: c for c in cases}
    result = {}
    for cid, (artifact_id, expected_sha) in FOCUS_ARTIFACTS.items():
        path = root / (artifact_id + ".zip")
        payload = path.read_bytes()
        require(sha256(payload) == expected_sha, "focus replay artifact SHA256 mismatch")
        prefix = f"pb-replay-results/expanded/{cid}/"
        with opened_zip(payload, "focus replay") as archive:
            summary_bytes = archive.read(prefix + "case-summary.json")
            summary = parse_json(summary_bytes)
            require(summary["case_id"] == cid and summary["stage"] == "expanded" and summary["status"] == "success" and
                    summary["source"]["commit"] == REPLAY_COMMIT, "focus replay identity differs")
            observations = summary["observations"]
            require([o["mode"] for o in observations] == ["baseline", "prepared_receptor"], "expanded replay mode order differs")
            reports = []
            sources = []
            for observation in observations:
                raw = archive.read(prefix + safe_member(observation["result_path"]))
                require(sha256(raw) == observation["result_sha256"], "focus result SHA256 mismatch")
                data = parse_json(raw)
                require(data["case_id"] == cid and data["stage"] == "expanded" and data["record_count"] == 64 and
                        data["status"] == "success" and data["source"] == summary["source"] and
                        data["bundle_sha256"] == summary["bundle_sha256"] and data["mode"] == observation["mode"],
                        "focus result/summary differs")
                require(data["input_ids"]["native_sha256"] == by_id[cid]["bindings"]["input_sha256s"]["native"] and
                        data["input_ids"]["receptor_sha256"] == by_id[cid]["bindings"]["input_sha256s"]["receptor"] and
                        data["input_ids"]["record_sha256s"] == [c["pose_artifact_sha256"] for c in by_id[cid]["candidates"]],
                        "focus replay is not the historical candidate/input sequence")
                reports.append(data)
                sources.append({"mode": observation["mode"], "result_path": prefix + observation["result_path"],
                                "result_sha256": observation["result_sha256"]})
            require(reports[0]["fullReport"] == reports[1]["fullReport"] and
                    reports[0]["legacy_outcomes"] == reports[1]["legacy_outcomes"], "focus replay scientific results differ")
            report = reports[0]["fullReport"]
            columns = report["columns"]
            require(len(columns) == len(set(columns)) == 126 and len(report["rows"]) == 64, "focus fullReport dimensions differ")
            rows = []
            for ordinal, (raw_row, candidate) in enumerate(zip(report["rows"], by_id[cid]["candidates"]), 1):
                require(raw_row["record_ordinal"] == ordinal and raw_row["record_sha256"] == candidate["pose_artifact_sha256"] and
                        len(raw_row["cells"]) == 126, "focus report row binding differs")
                values = dict(zip(columns, map(typed_value, raw_row["cells"])))
                require(all(type(values[name]) is bool for name in CHECKS), "focus validity checks are not booleans")
                failures = [name for name in CHECKS if not values[name]]
                require(failures == candidate["posebusters_failed_check_ids"] and
                        float(values["rmsd"]).hex() == float(candidate["rmsd_angstrom"]).hex(), "focus report/historical outcomes differ")
                require((values["most_extreme_relative_distance_protein"] >= 0.75) == values["minimum_distance_to_protein"] and
                        (values["volume_overlap_protein"] <= 0.075) == values["volume_overlap_with_protein"] and
                        (values["energy_ratio"] <= 100.0) == values["internal_energy"], "recorded thresholds and decisions differ")
                rows.append({"score_rank": ordinal, "proposal_index": candidate["proposal_index"],
                             "record_sha256": candidate["pose_artifact_sha256"], "failed_check_ids": failures,
                             **{key: values[key] for key in NUMERIC_FOCUS_COLUMNS}})
        result[cid] = {"source_artifact_id": artifact_id, "artifact_sha256": expected_sha,
                       "case_summary_sha256": sha256(summary_bytes), "source_run_id": REPLAY_RUN, "source_commit": REPLAY_COMMIT,
                       "result_bindings": sources, "record_count": 64, "columns": 126, "exact_cross_mode_report": True,
                       "numeric_distributions": {key: distribution([r[key] for r in rows]) for key in NUMERIC_FOCUS_COLUMNS},
                       "alignment_only_near_count": sum(r["kabsch_rmsd"] <= 2 and r["rmsd"] > 2 for r in rows),
                       "protein_distance_failures": sum("minimum_distance_to_protein" in r["failed_check_ids"] for r in rows),
                       "protein_volume_failures": sum("volume_overlap_with_protein" in r["failed_check_ids"] for r in rows),
                       "rows": rows,
                       "interpretation": "Kabsch RMSD is a conformation diagnostic only; fixed-receptor-frame RMSD remains the recovery metric."}
    return result


def summarize(cases: list[dict], engine_rows: dict) -> dict:
    denominator = len(cases)
    require(denominator > 0, "empty cohort")
    classifications = {}
    for k in TOP_K:
        counts = Counter(c["classifications"][f"top{k}"]["category"] for c in cases)
        require(set(counts) <= set(CATEGORIES) and sum(counts.values()) == denominator, "classification denominator differs")
        classifications[f"top{k}"] = {name: {"count": counts[name],
                                             "case_ids": [c["case_id"] for c in cases if c["classifications"][f"top{k}"]["category"] == name]}
                                        for name in CATEGORIES}
    candidates = [candidate for case in cases for candidate in case["candidates"]]
    quadrants = Counter(("near" if c["near_native"] else "far") + ("_valid" if c["joint_valid"] else "_invalid") for c in candidates)
    penalty = {direction: {"candidates": 0, "joint_invalid": 0, "near_native": 0, "valid_near_native": 0}
               for direction in ("decreased", "increased", "unchanged")}
    for c in candidates:
        bucket = penalty[c["refinement_penalty_direction"]]
        bucket["candidates"] += 1
        bucket["joint_invalid"] += not c["joint_valid"]
        bucket["near_native"] += c["near_native"]
        bucket["valid_near_native"] += c["near_native"] and c["joint_valid"]
    oracle = sum(bool(c["classifications"]["top5"]["known_near_native_count"]) for c in cases)
    valid_oracle = sum(bool(c["classifications"]["top5"]["known_valid_near_native_count"]) for c in cases)
    metrics = {}
    for engine, rows in engine_rows.items():
        require(len(rows) == denominator, "engine row denominator differs")
        require(all(row.get("status") in ("success", "failure") and
                    all(type(value) is int and value in (0, 1) for value in row["recoveries"].values())
                    for row in rows), "unobserved engine outcomes must not be converted to zero")
        counts = {key: sum(row["recoveries"][key] for row in rows)
                  for key in (f"{prefix}{k}" for prefix in ("top", "valid_top") for k in TOP_K)}
        metrics[engine] = {"denominator": denominator, "success_rows": sum(r["status"] == "success" for r in rows),
                           "failure_rows": sum(r["status"] == "failure" for r in rows),
                           "failure_codes": dict(Counter(r["failure_code"] for r in rows if r["status"] == "failure")),
                           "counts": counts, "rates": {key: value/denominator for key, value in counts.items()}}
    metrics["engine_v2"]["oracle_count"] = oracle
    metrics["engine_v2"]["valid_oracle_count"] = valid_oracle
    torsion = Counter()
    for case in cases:
        torsion.update(case["lineage"].get("torsion", {}))
    return {"fixed_case_denominator": denominator, "exclusive_case_categories": classifications,
            "candidate_evaluations": len(candidates),
            "candidate_quadrants": {key: quadrants[key] for key in ("near_valid", "near_invalid", "far_valid", "far_invalid")},
            "candidate_failure_checks": dict(sorted(Counter(check for c in candidates for check in c["posebusters_failed_check_ids"]).items())),
            "near_native_failure_checks": dict(sorted(Counter(check for c in candidates if c["near_native"] for check in c["posebusters_failed_check_ids"]).items())),
            "proposal_modes": dict(Counter(c["proposal_mode"] for c in candidates)),
            "selection_eligible_candidates": sum(c["selection_eligible"] for c in candidates),
            "recorded_refinement_penalty_cross_tab": penalty, "torsion_observations": dict(torsion),
            "refinement_coordinate_changes": {
                "post_v6_to_optimized": sum(c["lineage"]["v6_to_v7_coordinates_changed"] for c in candidates),
                "post_v6_to_selected": sum(c["lineage"]["v6_to_selected_coordinates_changed"] for c in candidates)},
            "engine_metrics": metrics,
            "fixed_pool_ranking_headroom": {f"valid_top{k}": {
                "observed_cases": metrics["engine_v2"]["counts"][f"valid_top{k}"], "oracle_upper_bound_cases": valid_oracle,
                "additional_case_upper_bound": valid_oracle - metrics["engine_v2"]["counts"][f"valid_top{k}"],
                "denominator": denominator} for k in TOP_K}}


def write_markdown(report: dict) -> str:
    s = report["summary"]
    labels = {"preparation_failure": "준비 실패", "incomplete_observation": "관측 불완전",
              "no_near_native": "평가된 최종 후보 전체에 RMSD ≤ 2 Å 없음", "near_native_only_invalid": "근접 후보가 모두 유효성 탈락",
              "valid_near_native_ranked_out": "유효 근접 후보가 Top-k 밖에 있음", "valid_near_native_recovered": "유효 근접 후보 회수"}
    lines = ["# 고정 32개 개발 사례의 도킹 실패 원인 분석", "",
             "이 보고서는 저장된 원시 실행 결과를 분석한다. 새 도킹, 재채점, 가중치 변경, 정확도 향상을 수행하거나 주장하지 않는다.", "",
             f"원본 실행: https://github.com/betelgeuze-kang/ligand-docking/actions/runs/{SOURCE_RUN}",
             f"원본 commit: `{SOURCE_COMMIT}`. 기존에 관찰한 development 집합이며 holdout이 아니다.", "",
             "## 고정 분모를 유지한 상호배타 분류", "",
             "near-native는 고정 수용체 좌표계에서 RMSD ≤ 2 Å, valid는 같은 포즈가 화학·기하 검사를 모두 통과한 경우다.", "",
             "후보 풀은 각 proposal에서 refinement 및 선택을 마친 뒤 평가한 64개 포즈다. 최종 후보에 근접 포즈가 없다는 사실만으로 생성 단계의 실패라고 확정할 수는 없다. 생성·최적화·선택 중 어느 단계에서 근접 포즈가 소실됐는지는 중간 좌표를 추가 평가해야 구분된다.", "",
             "| 분류 | Top1 기준 | Top3 기준 | Top5 기준 |", "|---|---:|---:|---:|"]
    for category in CATEGORIES:
        lines.append("| " + labels[category] + " | " + " | ".join(str(s["exclusive_case_categories"][f"top{k}"][category]["count"]) for k in TOP_K) + " |")
    q = s["candidate_quadrants"]
    lines += ["", f"실제로 평가한 후보는 {s['candidate_evaluations']:,}개다. 근접·유효 {q['near_valid']}개, 근접·무효 {q['near_invalid']}개, 원거리·유효 {q['far_valid']}개, 원거리·무효 {q['far_invalid']}개다.",
              "준비 실패 사례에 64개 실패 후보를 만들어 넣지 않았다. 사례 지표의 분모는 32로 유지한다.", "",
              "## 후보 순위만 바꿀 때의 상한", "",
              "현재 고정 후보 집합에서 valid oracle은 3/32다. valid Top1은 1/32로 최대 2개 사례의 순위 회수 여지가 있다. valid Top3와 Top5는 이미 3/32이므로 이 후보 집합의 순위 변경만으로 추가 사례를 회수할 수 없다.",
              "이 상한은 실제 새 랭킹 알고리즘의 달성 성능이 아니며, 정답 RMSD를 배포용 순위에 사용하지 않는다.", "",
              "| 근접 후보 보유 사례 | 근접 후보 점수 순위 | 그중 유효 후보 순위 |", "|---|---|---|"]
    for case in report["cases"]:
        if case.get("near_native_candidate_ranks"):
            lines.append(f"| {case['case_id']} | {case['near_native_candidate_ranks']} | {case['valid_near_native_candidate_ranks']} |")
    lines += ["", "### Top1 두 사례의 점수 항 대조", "",
              "아래 차이는 첫 valid-near 후보의 값에서 score Top1 후보의 값을 뺀 값이다. 낮은 score가 먼저 오므로 양수는 근접 후보가 순위에서 불리함을 뜻한다. 이미 가중치가 적용된 항이며 다시 가중치를 곱하지 않았다.", "",
              "| 사례 | Top1 RMSD | 첫 valid-near 순위 / RMSD | 총 score 차이 | typed VDW 차이 | desolvation 차이 |", "|---|---:|---:|---:|---:|---:|"]
    for case in report["cases"]:
        contrast = case.get("valid_near_native_score_contrast")
        if not contrast or contrast["best_scored_valid_near_native_rank"] == 1:
            continue
        first = case["candidates"][0]
        target = case["candidates"][contrast["best_scored_valid_near_native_rank"]-1]
        terms = contrast["weighted_component_differences_valid_near_minus_top1"]
        lines.append(f"| {case['case_id']} | {first['rmsd_angstrom']:.4f} Å | {target['score_rank']} / {target['rmsd_angstrom']:.4f} Å | {contrast['score_difference_valid_near_minus_top1']:+.6f} | {terms['typed_vdw']:+.6f} | {terms['desolvation_proxy']:+.6f} |")
    lines += ["", "두 사례의 rank-1 후보도 화학·기하 검사를 모두 통과한다. 따라서 유효성 필터만 추가해도 이 두 Top1 실패가 해결된다고 볼 수 없다. typed VDW 항이 두 대조에서 가장 큰 양의 차이를 보였지만, 두 사례만으로 새 가중치나 성능 향상을 정하지 않는다. 전체 8개 항과 순위별 수치는 JSON에 보존했다."]
    lines += ["", "## 유효성 실패 빈도", "", "한 후보가 여러 검사를 동시에 실패할 수 있으므로 아래 합계는 후보 수와 같지 않다.", "",
              "| 실패 검사 | 후보 수 | 실제 평가 후보 대비 |", "|---|---:|---:|"]
    for check, count in sorted(s["candidate_failure_checks"].items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f"| {check} | {count} | {100*count/s['candidate_evaluations']:.2f}% |")
    lines += ["", "근접·무효 후보 6개는 모두 화학 검사를 통과했고 단백질 최소 거리에서 실패했다. 5개는 단백질 부피 중첩도 실패했다. 이 후보들에는 내부 화학 항만 바꾸기보다 수용체 상대 배치와 clash 선택 규칙을 먼저 검토할 근거가 있다."]
    t = s["torsion_observations"]
    lines += ["", "## 실제 refinement 관측", "",
              f"journal에 기록된 {t['observed_candidates']:,}개 후보 중 torsion 평가 {t['evaluated_candidates']}개, trial 평가 {t['trial_evaluations']:,}회, 최종 torsion 선택 {t['selected_candidates']}개다.",
              "각 값은 source code에서 추정한 가능성이 아닌 이번 원시 journal에서 집계한 실제 기록이다.",
              f"post-V6와 post-V7 좌표 fingerprint가 다른 후보는 {s['refinement_coordinate_changes']['post_v6_to_optimized']}개이고, post-V6와 최종 선택 좌표가 다른 후보는 {s['refinement_coordinate_changes']['post_v6_to_selected']}개다. 평가 시도·좌표 변경·최종 선택을 같은 개수로 취급하지 않는다.",
              "quartic overlap penalty의 단위는 Å⁴이며 물리적 에너지나 결합 자유에너지가 아니다. 초기/최종 penalty 감소와 최종 유효성의 관계는 아래처럼 관찰됐지만, 초기 PoseBusters 결과가 없으므로 유효성 개선이나 인과관계를 뜻하지 않는다.", "",
              "| penalty 변화 | 후보 | 최종 joint-invalid | 최종 valid near-native |", "|---|---:|---:|---:|"]
    for direction, counts in s["recorded_refinement_penalty_cross_tab"].items():
        lines.append(f"| {direction} | {counts['candidates']} | {counts['joint_invalid']} | {counts['valid_near_native']} |")
    lines += ["", "## 6T88 / 6YSP 전체 평가표 진단", "",
              "두 사례의 64개 record를 과거 receipt와 새 replay fullReport에 SDF SHA로 연결했다. 새 baseline과 prepared 결과도 정확히 일치한다.", "",
              "| 사례 | 고정 좌표 RMSD 최솟값 | Kabsch RMSD 범위 | 단백질 거리 실패 | 단백질 부피 실패 |", "|---|---:|---:|---:|---:|"]
    for cid, focus in report.get("focus_replays", {}).items():
        d = focus["numeric_distributions"]
        lines.append(f"| {cid} | {d['rmsd']['minimum']:.4f} Å | {d['kabsch_rmsd']['minimum']:.4f}–{d['kabsch_rmsd']['maximum']:.4f} Å | {focus['protein_distance_failures']}/64 | {focus['protein_volume_failures']}/64 |")
    lines += ["", "| 사례 | 단백질 최소 상대거리 범위 | 단백질 부피 중첩 범위 | protein pair clash 범위 | energy ratio 범위 |", "|---|---:|---:|---:|---:|"]
    for cid, focus in report.get("focus_replays", {}).items():
        d = focus["numeric_distributions"]
        cols = ("most_extreme_relative_distance_protein", "volume_overlap_protein", "num_pairwise_clashes_protein", "energy_ratio")
        lines.append("| " + cid + " | " + " | ".join(f"{d[key]['minimum']:.6g}–{d[key]['maximum']:.6g}" for key in cols) + " |")
    lines += ["", "Kabsch 정렬로 얻은 작은 RMSD는 내부 형태를 살펴보기 위한 진단이다. 수용체에 대한 위치·방향을 맞춰버리는 정렬 결과를 도킹 성공으로 바꾸지 않았다.", "",
              "6YSP는 64개 모두 Kabsch RMSD ≤ 2 Å이나 고정 좌표 RMSD > 2 Å이며, 단백질 최소 상대거리 < 0.75 및 부피 중첩 > 0.075다. 이는 위치·방향과 수용체 충돌을 우선 조사할 근거다. 내부 에너지 문제도 일부 함께 있으므로 형태가 모두 물리적으로 유효하다는 뜻은 아니다. 6T88에서는 정렬만으로 임계값을 통과하는 경우가 60/64다.", "",
              "## 다음 수식·함수 실험의 우선순위", "",
              "1. 준비 실패 3개 사례의 large-ring 지원을 별도 회귀 시험으로 다룬다. 기존 실패를 성공으로 다시 표기하지 않는다.",
              "2. 최종 후보에 정답 근처가 없는 23개 사례에서는 생성·배치·방향 탐색 및 refinement 시점별 포즈를 평가해 근접 후보가 처음부터 없었는지 중간에 소실됐는지 구분한다. 동일 seed·후보 수·계산 예산에서 후보 oracle과 valid oracle을 함께 측정한다.",
              "3. 근접 후보가 있으나 유효하지 않은 6XM9, 6YQV, 6Z4N에서는 최적화 전후와 선택 전후의 clearance/내부 geometry를 추가 기록한다. 선택된 7개 torsion 결과와 평가됐지만 버려진 결과를 분리해 선택 규칙의 영향도 확인한다.",
              "4. Top1 순위 문제는 6YQW와 6Z0R의 rank-1 및 첫 valid-near 후보 대조를 바탕으로 score 함수의 typed VDW 접촉·충돌 성분을 분리 기록한다. 합계 score와 순위는 그대로 유지하는 관측 변경을 먼저 하고, 이후 한 항씩 사전 지정한 실험을 한다. 원본 가중치는 유지하고 holdout 전용 최종 평가는 분리한다.", "",
              "원인별 실험은 한 번에 한 변경을 비교한다. case-level fixed-denominator 성공률·실패율·시간·메모리와 candidate-level 유효성·oracle을 함께 기록한다.", "",
              "### 독립 분류식과 실험 판정", "",
              "준비된 사례 i의 후보 집합을 Cᵢ, Nᵢ = {c ∈ Cᵢ : RMSD(c) ≤ 2}, Vᵢ = {c ∈ Nᵢ : chemical(c) ∧ geometric(c)}, 점수 오름차순 상위 k개를 Rᵢ(k)로 둔다. 동점은 proposal_index 순서로 정한다.", "",
              "분류는 먼저 준비 실패와 관측 불완전을 분리한 뒤, Nᵢ가 비면 후보 미도달, Nᵢ가 있지만 Vᵢ가 비면 근접 후보 유효성 실패, Vᵢ가 있지만 Vᵢ ∩ Rᵢ(k)가 비면 순위 실패, 교집합이 있으면 회수로 정한다. 이 사례 분류는 상호배타이며 합계는 항상 32다. 근접·무효 후보 존재 여부는 별도 중복 플래그이므로 회수 사례에도 함께 있을 수 있다.", "",
              "- 생성 실험: seed·64 후보·시간 예산을 짝지어 보존하고 candidate oracle과 valid oracle을 먼저 비교한다. oracle이 그대로인데 Top1만 변하면 생성 개선과 구분한다.",
              "- 최적화 실험: proposal → post-V6 → post-V7 → selected의 같은 proposal ID를 유지하며 각 시점의 원래 PB checks·고정 좌표 RMSD를 새로 평가한다. 이를 통해 근접 후보 보존 여부와 충돌 개선 여부를 직접 비교한다. 기존 저장값만으로 중간 단계 PB 결과를 채우지 않는다.",
              "- 선택 실험: objective 감소, receptor 비증가, selection window 판정을 각각 기록하고 평가됨/실제 좌표 변경됨/최종 선택됨을 구분한다. 기준·패치 조건에 동일 evaluator identity를 결속한다.",
              "- 랭킹 실험: 같은 저장 후보의 score 항만 사용하는 변경을 따로 평가한다. 정답 RMSD와 native pose는 평가에만 사용한다. valid Top3/Top5의 고정 후보 상한이 이미 달성돼 있음을 함께 보고한다.",
              "- 판정: 32개 고정 분모, 준비 실패 및 typed failure, 실패 검사 ID, 사례별 성공/실패 전환과 시간을 모두 남긴다. development에 대한 개선 가설과 독립 holdout 검증 결과를 구분한다.", "",
              "## 증거와 재현", "",
              "`diagnosis.json`에는 각 사례의 후보·점수 항·분류·journal 해시·원시 artifact 해시·원래 지표와의 대조 결과가 있다. 전체 delivery inventory와 4개 development shard의 모든 payload 해시를 재계산하고, 96개 receipt, 32개 V2 journal, 29 × 64개 score receipt, 좌표 lineage 및 입력 파일의 결속을 검증했다. 이 분석기는 RDKit, PoseBusters, Torch를 import하지 않는다.",
              "`source-contracts.json`은 bcee827의 scorer·torsion refinement·benchmark 파일의 Git blob 및 SHA256, 유효성 check 목록과 원래 default weights를 기록한다. 이는 현재 소스 계약의 참조이며, 원시 실행은 위에 표시한 16980a8 commit이다. 관측 수치는 해당 원시 실행 receipt와 journal에서 계산했다.",
              "수치가 관찰되지 않은 시점의 RMSD, 초기 PB 유효성, 결합력, 자유에너지, 새 성공률을 추론하지 않았다.", "",
              f"원본 delivery SHA256: `{report['source']['delivery_sha256']}`.",
              f"분석기 SHA256: `{report['analysis_script_sha256']}`.", "",
              "```bash",
              "python tools/analyze_redocking_failures.py \\",
              "  --delivery /path/to/redocking-p0-p1-results-41697499611.zip \\",
              "  --replay-root /path/to/cloud-41778486589 \\",
              "  --output /new/path/diagnosis.json --markdown /new/path/README.md",
              "python -m unittest tests.unit.test_redocking_failure_diagnosis -v",
              "```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--delivery-sha256", default=DELIVERY_SHA256)
    parser.add_argument("--replay-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    outputs = [args.output.resolve()] + ([args.markdown.resolve()] if args.markdown else [])
    require(len(outputs) == len(set(outputs)) and all(p != args.delivery.resolve() and not p.exists() for p in outputs),
            "output already exists or overlaps an input")
    cases, engine_rows, source = read_frozen_delivery(args.delivery, expected_sha256=args.delivery_sha256)
    summary = summarize(cases, engine_rows)
    for engine, observed in summary["engine_metrics"].items():
        historical = source["historical_aggregate_metrics"][engine]
        require(observed["denominator"] == historical["denominator"] and observed["success_rows"] == historical["success_rows"] and
                observed["failure_rows"] == historical["typed_failure_rows"] and
                all(value == historical["counts"][key] for key, value in observed["counts"].items()),
                "independent diagnosis disagrees with recorded aggregate recovery metrics")
    v2 = source["historical_aggregate_metrics"]["engine_v2"]
    require(summary["candidate_evaluations"] == v2["candidate_success_count"] and
            summary["candidate_failure_checks"] == v2["candidate_failed_check_counts"] and
            summary["engine_metrics"]["engine_v2"]["oracle_count"] == v2["counts"]["oracle"] and
            summary["engine_metrics"]["engine_v2"]["valid_oracle_count"] == v2["counts"]["valid_oracle"],
            "independent diagnosis disagrees with candidate/oracle totals")
    focus = read_focus_replays(args.replay_root, cases) if args.replay_root else {}
    report = {"schema_id": "betelgeuze.redocking_failure_diagnosis/1.0.0", "status": "verified",
              "created_at_utc": datetime.now(timezone.utc).isoformat(), "analysis_script_sha256": sha256(Path(__file__).read_bytes()),
              "source": source, "summary": summary, "cases": cases, "focus_replays": focus,
              "molecular_execution_performed": False, "scoring_or_ranking_changed": False,
              "new_accuracy_improvement_measured": False, "historical_aggregate_metrics_match": True,
              "classification_contract": {
                  "rmsd_threshold_angstrom": RMSD_THRESHOLD, "near_native": "recorded fixed-receptor-frame RMSD <= 2.0",
                  "candidate_pool_stage": "selected final pose per proposal after refinement; lack of near-native final poses does not establish the failing generation/optimization stage",
                  "joint_valid": "chemical_valid AND geometric_valid for the same candidate",
                  "ranking": "finite successful score ascending, then proposal_index; selection_eligible is not an added filter",
                  "exclusive_categories": list(CATEGORIES), "overlapping_flags": "invalid-near candidates can coexist with valid-near candidates",
                  "missing_observation": "incomplete_observation, never no_near_native; preparation failures retain zero actual candidates",
                  "historical_score_sum": "Eight already-weighted terms added in original source order with Python 3.10 float accumulation",
              },
              "observed_data_coverage": {
                  "fixed_development_cases": 32, "engine_outcomes": 96,
                  "development_sealed_archives": len(source["archives"]),
                  "verified_development_payload_files": sum(a["verified_payload_files"] for a in source["archives"]),
                  "v2_journals": len(cases), "v2_journal_events": sum(c["bindings"]["journal"]["event_count"] for c in cases),
                  "coordinate_snapshots": sum(c["lineage"]["coordinate_snapshot_count"] for c in cases),
                  "score_receipts": sum(c["lineage"]["score_receipts_verified"] for c in cases),
                  "focused_full_report_records": sum(f["record_count"] for f in focus.values()),
                  "missing_fields": ["PB checks and fixed-frame RMSD for preselected coordinate stages",
                                     "typed VDW attractive/repulsive subcomponents beyond the retained weighted aggregate",
                                     "fullReport numerical diagnostics outside the two retained candidate64 replay cases"],
              },
              "limitations": [
                  "One fixed seed on previously observed development cases; no holdout or population generalization claim.",
                  "Initial/post-V6/post-V7 coordinates are retained, but PB/RMSD was evaluated only on the selected final poses in this source run.",
                  "Recorded quartic-overlap penalty is a geometric proxy in angstrom^4, not physical/free energy.",
                  "Stage timings can nest; they are not summed as disjoint work.",
                  "Raw fullReport numerical diagnostics cover only the two retained candidate64 replay cases.",
                  "Oracle ranking headroom is a bound for the unchanged recorded pool, not performance of a new deployable ranking function.",
              ]}
    require(sha256(args.delivery.read_bytes()) == DELIVERY_SHA256, "source delivery changed during analysis")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.markdown.open("x", encoding="utf-8") as output:
            output.write(write_markdown(report))
    print(json.dumps({"status": report["status"], "output": str(args.output), "cases": len(cases),
                      "candidate_evaluations": summary["candidate_evaluations"], "focus_replays": sorted(focus)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
