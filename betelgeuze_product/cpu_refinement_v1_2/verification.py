"""Read-only structural verification of comparison/selection artifacts.

Hashes and internal consistency are not signatures or independent scientific
validation. This does not rerun the scorer or assert historical execution.
"""
from __future__ import annotations

from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from betelgeuze_engine_v2.docking.scorer_v1 import _sha256 as score_receipt_digest
from .comparison import choose_variant
from .fixed_receptor import FIXED_REPORT_SCHEMA, FIXED_POLICY_ID
from .evidence_contracts import (
    REPORT_SCHEMA, LEGACY_REPORT_SCHEMA, POLICY_ID, same, selection_config,
    verify_execution_evidence,
)
from .provenance import ResearchError, canonical, decode_coordinates, digest, finite, integer
from .selection import candidate_from_row, select_final_candidates, refinement_admissible


def verify_report(report: dict) -> dict:
    try:
        return _verify_report(report)
    except ResearchError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise ResearchError("malformed or inconsistent comparison evidence") from exc


def _verify_report(report: dict) -> dict:
    if report.get("schema_id") not in {REPORT_SCHEMA, LEGACY_REPORT_SCHEMA, FIXED_REPORT_SCHEMA}:
        raise ResearchError("unsupported comparison report")
    if digest({k: v for k, v in report.items() if k != "report_sha256"}) != report.get("report_sha256"):
        raise ResearchError("comparison report digest mismatch")
    if any(report.get(flag) is not False for flag in ("scientifically_validated", "customer_execution_allowed", "claim_safe")):
        raise ResearchError("research report cannot promote execution or scientific claims")
    fixed = report["schema_id"] == FIXED_REPORT_SCHEMA
    current = report["schema_id"] in {REPORT_SCHEMA, FIXED_REPORT_SCHEMA}
    cap = report.get("max_internal_increase_kcal_per_mol")
    if current:
        same(report["selection_policy_id"], FIXED_POLICY_ID if fixed else POLICY_ID, "selection policy")
    n = integer(report["atom_count"], 1, 256)
    verify_execution_evidence(report)
    k = integer(report["budget"]["top_k"], 1, 256)
    arms = report["arms"]
    if set(arms) != {"baseline", "refined"}:
        raise ResearchError("comparison arms missing")
    for arm in arms.values():
        rows = arm["rows"]
        if not rows or len(rows) != arm["candidate_count"] or len(rows) > 256:
            raise ResearchError("candidate denominator mismatch")
        if len({row["candidate_id"] for row in rows}) != len(rows):
            raise ResearchError("duplicate arm candidate identity")
        succeeded = 0
        for row in rows:
            if type(row["succeeded"]) is not bool:
                raise ResearchError("success flag must be boolean")
            if row["succeeded"]:
                succeeded += 1
                score = finite(row["score"])
                terms = row["terms"]
                if (score.hex() != terms["total_score_binary64_hex"]
                        or terms["authority_input_receipt_sha256"] != report["authority_input_receipt_sha256"]
                        or score_receipt_digest({key: value for key, value in terms.items() if key != "receipt_sha256"}) != terms["receipt_sha256"]):
                    raise ResearchError("score value or receipt does not match retained terms")
                xyz = decode_coordinates(row["coordinates_binary64_hex"], n)[0]
                if coordinate_fingerprint(xyz) != row["coordinates_sha256"]:
                    raise ResearchError("arm coordinate digest mismatch")
                if row["terms"]["proposal_fingerprint_sha256"] != row["result_proposal_fingerprint_sha256"]:
                    raise ResearchError("score terms are cross-wired")
        if succeeded != arm["success_count"] or len(rows) - succeeded != arm["failure_count"]:
            raise ResearchError("failure-inclusive counts mismatch")
    attempts = report["attempts"]
    if len(attempts) != arms["refined"]["candidate_count"]:
        raise ResearchError("attempt denominator mismatch")
    for row, attempt in zip(arms["refined"]["rows"], attempts, strict=True):
        if digest({k: v for k, v in attempt.items() if k != "receipt_sha256"}) != attempt["receipt_sha256"]:
            raise ResearchError("attempt receipt mismatch")
        if (attempt["source_proposal_fingerprint_sha256"] != row["proposal_fingerprint_sha256"]
                or attempt["candidate_id"] != row["candidate_id"] or attempt["proposal_index"] != row["proposal_index"]
                or attempt["evaluator"] != report["evaluator"]
                or attempt["implementation_source_sha256"] != report["implementation_source_sha256"]):
            raise ResearchError("attempt source identity mismatch")
        for phase in ("pre", "post"):
            key = f"{phase}_coordinates_sha256"
            if key in attempt:
                xyz = decode_coordinates(attempt[f"{phase}_coordinates_binary64_hex"], n)[0]
                if coordinate_fingerprint(xyz) != attempt[key]:
                    raise ResearchError("attempt coordinates mismatch")
        if attempt["status"] == "success":
            if float(attempt["energy_delta"]).hex() != (attempt["final_energy"] - attempt["initial_energy"]).hex():
                raise ResearchError("attempt energy delta mismatch")
            if row["succeeded"] and row["coordinates_sha256"] != attempt["post_coordinates_sha256"]:
                raise ResearchError("returned coordinates were not the refined coordinates")
        elif attempt["status"] != "failure":
            raise ResearchError("invalid attempt status")
    first = report["per_arm_selection"]["baseline"]
    config = selection_config(report["selection_config"] if current else first["config"], k)
    descriptor_doc = first["score_descriptor"]
    descriptor = DockingScoreDescriptor(**{**descriptor_doc, "direction": ScoreDirection(descriptor_doc["direction"])})
    from betelgeuze_engine_v2.docking.scorer_v1 import SCORER_V1_SCORE_ID, SCORER_V1_APPLICABILITY_DOMAIN_ID
    expected_descriptor = DockingScoreDescriptor(
        SCORER_V1_SCORE_ID, ScoreDirection.MINIMIZE, None,
        "uncalibrated_dimensionless_chemistry_pose_ordering_score", False,
        applicability_domain_id=SCORER_V1_APPLICABILITY_DOMAIN_ID)
    same(descriptor_doc, expected_descriptor.to_dict(), "uncalibrated scorer descriptor")
    for name in arms:
        raw = select_final_candidates(
            [candidate_from_row(row, name) for row in arms[name]["rows"] if row["succeeded"] and row["selection_eligible"]],
            descriptor, config, n)
        expected = raw
        if current:
            same(raw, report["raw_per_arm_selection"][name], "raw diagnostic selection")
            if name == "refined":
                expected = select_final_candidates(
                    [candidate_from_row(row, name) for row, attempt in zip(arms[name]["rows"], attempts, strict=True)
                     if refinement_admissible(row, attempt, report["comparison"]["require_convergence_for_selection"], cap)],
                    descriptor, config, n)
        same(expected, report["per_arm_selection"][name], "arm final selection")
    candidates, pairs = [], []
    if report["mode"] == "same_candidates":
        for before, after, attempt in zip(arms["baseline"]["rows"], arms["refined"]["rows"], attempts, strict=True):
            if before["proposal_fingerprint_sha256"] != after["proposal_fingerprint_sha256"]:
                raise ResearchError("paired source identity mismatch")
            if before["succeeded"] and before["coordinates_sha256"] != attempt["pre_coordinates_sha256"]:
                raise ResearchError("original coordinates are inconsistent")
            choice, reason = choose_variant(before, after, attempt, report["comparison"]["require_convergence_for_selection"], cap)
            pairs.append({"candidate_id": before["candidate_id"], "variant": choice, "reason": reason})
            if choice != "none":
                candidates.append(candidate_from_row(before if choice == "baseline" else after, choice))
        expected = select_final_candidates(candidates, descriptor, config, n)
        if canonical(expected) != canonical(report["final_selection"]):
            raise ResearchError("cross-variant Top-K is inconsistent")
    elif report["mode"] != "equal_work_budget" or report["final_selection"] is not None:
        raise ResearchError("unpaired arms cannot carry a combined selection")
    if canonical(pairs) != canonical(report["paired_decisions"]):
        raise ResearchError("variant selection decisions are inconsistent")
    return {"structural_verification_passed": True, "report_sha256": report["report_sha256"],
            "scientifically_validated": False, "scoring_reexecuted": False,
            "verification_schema_id": "cpu_fixed_receptor_evidence_verification/1.0.0" if fixed else "cpu_evidence_verification/1.2.1",
            "legacy_per_arm_selection_is_diagnostic": not current,
            "input_binding_evidence_present": current and report["request_binding"] is not None}
