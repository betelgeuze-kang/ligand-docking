from __future__ import annotations

from copy import deepcopy
import io
import math
from pathlib import Path
import tarfile

import pytest

import tools.build_engine_v2_source_paired_clearance_v11_evidence as evidence


def _non_target(index: int) -> dict[str, object]:
    return {
        "proposal_index": index,
        "proposal_mode": "uniform_fallback",
        "refinement_receipt_payload": {
            "schema_id": evidence.EXPECTED_RECEIPT_SCHEMA_ID,
            "clearance_measurement_evaluated": False,
            "clearance_measurement_unavailable_reason": (
                "not_source_paired_rescue_target"
            ),
            "clearance_radii_policy_sha256": "",
            "clearance_ligand_atom_count": 0,
            "clearance_receptor_atom_count": 0,
            "clearance_full_cartesian_pair_count": 0,
            "clearance_pair_count_bound": (
                evidence.EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
            ),
            "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
            "optimized_coordinates_sha256": "",
        },
    }


def _target(
    index: int,
    *,
    torsion_evaluated: bool = True,
    variant_available: bool = True,
    optimized_gap: float = -1.5,
) -> dict[str, object]:
    baseline_coordinates_sha256 = f"{index + 1000:064x}"
    optimized_coordinates_sha256 = (
        f"{index + 1:064x}" if variant_available else baseline_coordinates_sha256
    )
    if not variant_available:
        optimized_gap = -2.0
    return {
        "proposal_index": index,
        "proposal_mode": "uniform_torsion_rescue_variant",
        "refinement_receipt_payload": {
            "schema_id": evidence.EXPECTED_RECEIPT_SCHEMA_ID,
            "torsion_evaluated": torsion_evaluated,
            "torsion_variant_available": variant_available,
            "torsion_selected": False,
            "baseline_coordinates_sha256": baseline_coordinates_sha256,
            "post_coordinates_sha256": baseline_coordinates_sha256,
            "clearance_measurement_evaluated": True,
            "clearance_measurement_unavailable_reason": "none",
            "clearance_radii_policy_sha256": (
                evidence.EXPECTED_CLEARANCE_RADII_POLICY_SHA256
            ),
            "clearance_ligand_atom_count": 20,
            "clearance_receptor_atom_count": 100,
            "clearance_full_cartesian_pair_count": 2_000,
            "clearance_pair_count_bound": (
                evidence.EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
            ),
            "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": ((-2.0).hex()),
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": (
                optimized_gap.hex()
            ),
            "optimized_coordinates_sha256": optimized_coordinates_sha256,
        },
    }


def _results() -> dict[str, dict[str, object]]:
    target_cases = {
        "5SD5_HWI",
        "5SIS_JSM",
        "6T88_MWQ",
        "6TW5_9M2",
        "6TW7_NZB",
        "6VTA_AKN",
        "6WTN_RXT",
    }
    results: dict[str, dict[str, object]] = {}
    target_ordinal = 0
    uncovered_ordinal = 0
    for case_id in evidence.EXPECTED_CASE_IDS:
        candidates: list[dict[str, object]] = []
        if case_id != evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID:
            for index in range(64):
                if case_id in target_cases and index < 4:
                    if case_id == "6T88_MWQ":
                        optimized_gap = -2.0
                    elif uncovered_ordinal < 10:
                        optimized_gap = (
                            math.nextafter(-2.0, math.inf)
                            if uncovered_ordinal == 0
                            else -1.5
                        )
                        uncovered_ordinal += 1
                    elif uncovered_ordinal < 23:
                        optimized_gap = -2.0
                        uncovered_ordinal += 1
                    else:
                        optimized_gap = -2.25
                        uncovered_ordinal += 1
                    candidates.append(
                        _target(
                            index,
                            torsion_evaluated=target_ordinal != 0,
                            variant_available=target_ordinal not in {10, 11},
                            optimized_gap=optimized_gap,
                        )
                    )
                    target_ordinal += 1
                else:
                    candidates.append(_non_target(index))
        results[case_id] = {
            "engine_v2_diagnostics": {
                "candidates": candidates,
                "ligand_atom_count": 20 if candidates else 0,
                "receptor_atom_count": 100 if candidates else 0,
            },
        }
    return results


def test_clearance_summary_requires_uniform_v11_and_exact_denominators() -> None:
    summary = evidence._clearance_summary(_results())

    assert summary["uniform_v11_candidate_receipt_count"] == 512
    assert summary["non_target_empty_telemetry_count"] == 484
    assert summary["pair_bound_unavailable_count"] == 0
    assert summary["torsion"] == evidence.EXPECTED_TORSION_COUNTS
    assert summary["all_fixed_rescue_targets"]["count"] == 28
    assert summary["proposal_oracle_uncovered_targets"]["count"] == 24
    assert summary["all_fixed_rescue_targets"]["gap_change_counts"] == {
        "improved": 10,
        "equal": 17,
        "regressed": 1,
    }
    assert summary["proposal_oracle_uncovered_targets"]["gap_change_counts"] == {
        "improved": 10,
        "equal": 13,
        "regressed": 1,
    }
    for cohort in (
        summary["all_fixed_rescue_targets"],
        summary["proposal_oracle_uncovered_targets"],
    ):
        for field in (
            "baseline_v6_minimum_vdw_surface_gap_angstrom",
            "optimized_minimum_vdw_surface_gap_angstrom",
        ):
            assert float.fromhex(cohort[field]["maximum_binary64_hex"]) < 0.0
    first_payload = _results()["5SD5_HWI"]["engine_v2_diagnostics"]["candidates"][0][
        "refinement_receipt_payload"
    ]
    baseline = float.fromhex(
        first_payload["baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex"]
    )
    optimized = float.fromhex(
        first_payload["optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"]
    )
    assert optimized == math.nextafter(baseline, math.inf)
    assert optimized > baseline


@pytest.mark.parametrize(
    "drift",
    (
        "schema",
        "pair_product",
        "non_target_value",
        "diagnostic_ligand_count",
        "non_target_count",
        "unavailable_coordinates",
        "unavailable_gap",
        "unavailable_non_bool",
        "available_post_coordinates",
    ),
)
def test_clearance_summary_rejects_resealed_drift(drift: str) -> None:
    results = deepcopy(_results())
    first = results["5SD5_HWI"]["engine_v2_diagnostics"]["candidates"][0]
    unavailable = results["6T88_MWQ"]["engine_v2_diagnostics"]["candidates"][2]
    non_target = results["6M2B_EZO"]["engine_v2_diagnostics"]["candidates"][0]
    if drift == "schema":
        first["refinement_receipt_payload"]["schema_id"] = (
            "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0"
        )
    elif drift == "pair_product":
        first["refinement_receipt_payload"]["clearance_full_cartesian_pair_count"] += 1
    elif drift == "non_target_value":
        non_target["refinement_receipt_payload"]["optimized_coordinates_sha256"] = (
            "a" * 64
        )
    elif drift == "diagnostic_ligand_count":
        results["5SD5_HWI"]["engine_v2_diagnostics"]["ligand_atom_count"] = 21
    elif drift == "unavailable_coordinates":
        unavailable["refinement_receipt_payload"]["optimized_coordinates_sha256"] = (
            "f" * 64
        )
    elif drift == "unavailable_gap":
        unavailable["refinement_receipt_payload"][
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex"
        ] = (-1.5).hex()
    elif drift == "unavailable_non_bool":
        unavailable["refinement_receipt_payload"]["torsion_variant_available"] = 0
    elif drift == "available_post_coordinates":
        first["refinement_receipt_payload"]["post_coordinates_sha256"] = "e" * 64
    else:
        non_target["refinement_receipt_payload"]["clearance_ligand_atom_count"] = 1

    with pytest.raises(ValueError):
        evidence._clearance_summary(results)


def test_walltime_receipt_is_strict_and_binary64_encoded() -> None:
    path = "run.walltime.txt"
    members = {
        path: (
            b"elapsed_seconds=10.5\n"
            b"user_seconds=11.0\n"
            b"system_seconds=0.5\n"
            b"max_rss_kb=1024\n"
            b"exit_status=0\n"
        )
    }

    parsed = evidence._walltime(members, path, lane="fixture")

    assert parsed["elapsed_seconds_binary64_hex"] == (10.5).hex()
    assert parsed["maximum_rss_kb"] == 1024
    assert parsed["exit_status"] == 0

    valid = members[path]
    members[path] = valid + b"elapsed_seconds=99.0\n"
    with pytest.raises(ValueError, match="wall-time fields"):
        evidence._walltime(members, path, lane="fixture")

    members[path] = valid
    members[path] = members[path].replace(b"exit_status=0", b"exit_status=1")
    with pytest.raises(ValueError, match="wall-time values"):
        evidence._walltime(members, path, lane="fixture")


def test_compact_analysis_is_preserved_without_consuming_term_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "5SD5_HWI"
    monkeypatch.setattr(evidence, "EXPECTED_CASE_IDS", (case_id,))
    path = "analysis.json"
    run_root = "run"
    source_path = f"{run_root}/receipts/engine_v2/{case_id}.json"
    source_receipts = {source_path: "a" * 64}
    projection: dict[str, object] = {
        "schema_id": evidence.EXPECTED_ANALYSIS_SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "contains_fresh_internal_blind_holdout": False,
        "claimable": False,
        "case_ids": [case_id],
        "source_receipts_sha256": source_receipts,
        "case_count": 1,
        "scored_case_count": 1,
        "candidate_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "oracle_2a_recovery_case_count": 1,
        "full_top1_recovery_case_count": 1,
        "full_top5_recovery_case_count": 1,
        "term_summary": {"legacy": "opaque"},
    }
    payload = {**projection, "report_sha256": evidence._sha256_payload(projection)}
    members = {path: evidence._canonical_bytes(payload) + b"\n"}

    observed = evidence._analysis(
        members,
        path,
        lane="fixture",
        run_root=run_root,
        receipt_hashes={case_id: "a" * 64},
    )
    assert observed["report_sha256"] == payload["report_sha256"]

    tampered = deepcopy(payload)
    tampered["term_summary"] = {"different": "legacy bytes"}
    tampered["report_sha256"] = evidence._sha256_payload(
        {key: value for key, value in tampered.items() if key != "report_sha256"}
    )
    members[path] = evidence._canonical_bytes(tampered) + b"\n"
    assert evidence._analysis(
        members,
        path,
        lane="fixture",
        run_root=run_root,
        receipt_hashes={case_id: "a" * 64},
    )["report_sha256"] == tampered["report_sha256"]

    with pytest.raises(ValueError, match="restored receipts"):
        evidence._analysis(
            members,
            path,
            lane="fixture",
            run_root=run_root,
            receipt_hashes={case_id: "b" * 64},
        )


def test_deterministic_tar_uses_sorted_fixed_metadata() -> None:
    members = {"z/member": b"z", "a/member": b"a"}

    first = evidence._deterministic_tar_bytes(members)
    second = evidence._deterministic_tar_bytes(dict(reversed(tuple(members.items()))))

    assert first == second
    with tarfile.open(fileobj=io.BytesIO(first), mode="r:") as archive:
        rows = archive.getmembers()
    assert [row.name for row in rows] == ["a/member", "z/member"]
    assert all(row.mode == 0o600 for row in rows)
    assert all((row.uid, row.gid, row.mtime) == (0, 0, 0) for row in rows)


def test_manifest_and_tar_reject_member_hash_drift() -> None:
    members = {f"members/{index:02d}.txt": str(index).encode() for index in range(59)}
    manifest_raw = evidence._manifest_bytes(members)
    manifest = evidence._parse_manifest(manifest_raw)
    tar_raw = evidence._deterministic_tar_bytes(members)

    assert evidence._tar_members(tar_raw, manifest) == members

    noncanonical_buffer = io.BytesIO()
    with tarfile.open(
        fileobj=noncanonical_buffer,
        mode="w",
        format=tarfile.GNU_FORMAT,
    ) as archive:
        for name in reversed(sorted(members)):
            info = tarfile.TarInfo(name)
            info.size = len(members[name])
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(members[name]))
    with pytest.raises(ValueError, match="canonical deterministic layout"):
        evidence._tar_members(noncanonical_buffer.getvalue(), manifest)

    tampered = dict(manifest)
    tampered["members/00.txt"] = "0" * 64
    with pytest.raises(ValueError, match="payload hash"):
        evidence._tar_members(tar_raw, tampered)


def test_reviewed_evidence_identities_are_pinned() -> None:
    assert len(evidence.OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1) == 40
    assert all(
        character in "0123456789abcdef"
        for character in evidence.OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1
    )
    assert evidence.EXPECTED_RECEIPT_SCHEMA_ID == (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
    )
    assert not hasattr(evidence, "_typed_development_result")
    for value in (
        evidence.EXPECTED_EVIDENCE_ARCHIVE_SHA256,
        evidence.EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256,
        evidence.EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256,
        evidence.EXPECTED_REPORT_SHA256,
    ):
        assert evidence._is_sha256(value)
    assert set(evidence.EXPECTED_EXECUTION_CONTRACT_SHA256_BY_LANE_CASE) == {
        "baseline",
        "rescue",
    }
    assert all(
        set(pins) == set(evidence.EXPECTED_CASE_IDS)
        and all(evidence._is_sha256(value) for value in pins.values())
        for pins in evidence.EXPECTED_EXECUTION_CONTRACT_SHA256_BY_LANE_CASE.values()
    )
    assert evidence.EXPECTED_EVIDENCE_MEMBER_COUNT == 59
    assert evidence.REPORT_PATH.endswith("6a749540-audit.json")


def _lane_fixture() -> tuple[dict[str, object], dict[str, object]]:
    pairs = [
        {"target_proposal_index": index + 28, "parent_proposal_index": index}
        for index in range(28)
    ]
    allocation: dict[str, object] = {
        "authority_rotor_count": 28,
        "rescue_target_parent_pairs": pairs,
    }
    allocation["allocation_sha256"] = evidence._sha256_payload(allocation)
    proposal_receipt: dict[str, object] = {"allocation": allocation}
    proposal_receipt["receipt_sha256"] = evidence._sha256_payload(proposal_receipt)
    baseline_candidates: list[dict[str, object]] = []
    rescue_candidates: list[dict[str, object]] = []
    for index in range(57):
        parent_index = index - 28
        target = 28 <= index < 56
        coordinate = f"coordinate-{parent_index if target else index}"
        baseline_candidates.append(
            {
                "proposal_index": index,
                "proposal_mode": "uniform_fallback",
                "coordinate_fingerprint_sha256": (
                    f"baseline-target-{index}" if target else coordinate
                ),
            }
        )
        rescue_candidate: dict[str, object] = {
            "proposal_index": index,
            "proposal_mode": (
                evidence.PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
                if target
                else "uniform_fallback"
            ),
            "coordinate_fingerprint_sha256": coordinate,
        }
        if target:
            rescue_candidate.update(
                {
                    "torsion_rescue_parent_proposal_index": parent_index,
                    "refinement_receipt_payload": {
                        "source_paired_parent_proposal_index": parent_index,
                        "source_paired_torsion_rescue_pairs": pairs,
                        "source_paired_torsion_rescue_allocation_sha256": allocation[
                            "allocation_sha256"
                        ],
                    },
                }
            )
        rescue_candidates.append(rescue_candidate)
    artifacts = {
        "receptor_artifact_sha256": "a" * 64,
        "reference_artifact_sha256": "b" * 64,
        "native_artifact_sha256": "c" * 64,
        "seed_artifact_sha256": "d" * 64,
    }
    baseline = {
        "results": {
            "fixture": {
                **artifacts,
                "engine_v2_diagnostics": {"candidates": baseline_candidates},
            }
        }
    }
    rescue = {
        "results": {
            "fixture": {
                **artifacts,
                "engine_v2_diagnostics": {
                    "candidates": rescue_candidates,
                    "source_paired_torsion_rescue_proposal_receipt": proposal_receipt,
                },
            }
        }
    }
    return baseline, rescue


def test_lane_comparison_binds_changed_indices_to_exact_rescue_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evidence, "EXPECTED_CASE_IDS", ("fixture",))
    baseline, rescue = _lane_fixture()
    proposal = rescue["results"]["fixture"]["engine_v2_diagnostics"][
        "source_paired_torsion_rescue_proposal_receipt"
    ]
    pairs = proposal["allocation"]["rescue_target_parent_pairs"]
    monkeypatch.setattr(
        evidence,
        "_v11_rescue_allocation",
        lambda diagnostics, candidates, *, case_id: (28, pairs),
    )

    comparison = evidence._lane_comparison(baseline, rescue)

    assert comparison["baseline_to_rescue_coordinate_change_candidate_count"] == 28
    assert comparison["rescue_to_parent_coordinate_duplicate_candidate_count"] == 28

    baseline_candidates = baseline["results"]["fixture"]["engine_v2_diagnostics"][
        "candidates"
    ]
    rescue_candidates = rescue["results"]["fixture"]["engine_v2_diagnostics"][
        "candidates"
    ]
    baseline_candidates[28]["coordinate_fingerprint_sha256"] = rescue_candidates[28][
        "coordinate_fingerprint_sha256"
    ]
    baseline_candidates[56]["coordinate_fingerprint_sha256"] = "swapped-nontarget"

    with pytest.raises(ValueError, match="contradict the allocation"):
        evidence._lane_comparison(baseline, rescue)


def test_lane_comparison_binds_unavailable_variant_to_baseline_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evidence, "EXPECTED_CASE_IDS", ("fixture",))
    baseline, rescue = _lane_fixture()
    proposal = rescue["results"]["fixture"]["engine_v2_diagnostics"][
        "source_paired_torsion_rescue_proposal_receipt"
    ]
    pairs = proposal["allocation"]["rescue_target_parent_pairs"]
    monkeypatch.setattr(
        evidence,
        "_v11_rescue_allocation",
        lambda diagnostics, candidates, *, case_id: (28, pairs),
    )
    baseline_candidates = baseline["results"]["fixture"]["engine_v2_diagnostics"][
        "candidates"
    ]
    rescue_candidates = rescue["results"]["fixture"]["engine_v2_diagnostics"][
        "candidates"
    ]
    parent_coordinate = baseline_candidates[0]["coordinate_fingerprint_sha256"]
    payload = rescue_candidates[28]["refinement_receipt_payload"]
    payload.update(
        {
            "torsion_variant_available": False,
            "baseline_coordinates_sha256": parent_coordinate,
            "post_coordinates_sha256": parent_coordinate,
            "optimized_coordinates_sha256": parent_coordinate,
        }
    )

    evidence._lane_comparison(baseline, rescue)

    payload.update(
        {
            "baseline_coordinates_sha256": "self-consistent-drift",
            "post_coordinates_sha256": "self-consistent-drift",
            "optimized_coordinates_sha256": "self-consistent-drift",
        }
    )
    with pytest.raises(ValueError, match="baseline parent"):
        evidence._lane_comparison(baseline, rescue)


def _frozen_rescue_policy() -> dict[str, object]:
    projection: dict[str, object] = {
        "schema_id": evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SCHEMA_ID,
        "policy_id": evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROFILE_ID,
        "base_guided_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        ),
        "candidate_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "maximum_variant_count": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        ),
        "source_pair_authority": "base_uniform_v3_ensemble_receipt",
        "variant_target_selection": (
            "rounded_even_spacing_across_ordered_v3_target_indices"
        ),
        "authority_rotor_required": True,
        "proposal_objects_and_coordinates_unchanged": True,
        "selected_parent_proposal_objects_retained": True,
        "ordinary_v3_and_rescue_target_parent_unions_disjoint": True,
        "candidate_denominator_changed": False,
        "rmsd_posebusters_native_rank_or_score_used_for_allocation": False,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "product_promotion_eligible": False,
        "public_claim_eligible": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    assert evidence._sha256_payload(projection) == (
        evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
    )
    return {
        **projection,
        "fingerprint_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        ),
    }


def _allocation_fixture() -> tuple[dict[str, object], list[dict[str, object]]]:
    authority_sha256 = "a" * 64
    guidance_context_sha256 = "b" * 64
    budget_sha256 = "c" * 64
    all_pairs = [
        {"target_proposal_index": 8 + index, "parent_proposal_index": 24 + index}
        for index in range(16)
    ]
    rescue_targets = {8, 13, 18, 23}
    rescue_pairs = [
        row for row in all_pairs if row["target_proposal_index"] in rescue_targets
    ]
    allocation: dict[str, object] = {
        "schema_id": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_ALLOCATION_SCHEMA_ID
        ),
        "authenticated_input_receipt_sha256": authority_sha256,
        "guidance_context_sha256": guidance_context_sha256,
        "budget_sha256": budget_sha256,
        "rescue_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        ),
        "base_guided_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        ),
        "candidate_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "authority_rotor_count": 4,
        "v3_target_parent_pairs": [
            row
            for row in all_pairs
            if row["target_proposal_index"] not in rescue_targets
        ],
        "rescue_target_parent_pairs": rescue_pairs,
        "rescue_variant_count": 4,
        "rescue_variant_cap": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
        ),
        "selected_parent_proposal_objects_retained": True,
        "candidate_denominator_changed": False,
        "result_dependent_allocation": False,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "claim_safe": False,
    }
    allocation["allocation_sha256"] = evidence._sha256_payload(allocation)
    candidate_slots = [
        {
            "proposal_index": index,
            "candidate_id": f"fixture-{index}",
            "proposal_fingerprint_sha256": f"{index + 1:064x}",
            "coordinate_fingerprint_sha256": f"{index + 65:064x}",
            "torsion_metadata_sha256": f"{index + 129:064x}",
        }
        for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
    ]
    rescue_parent_by_target = {
        row["target_proposal_index"]: row["parent_proposal_index"]
        for row in rescue_pairs
    }
    baseline_parent_by_target = {
        row["target_proposal_index"]: row["parent_proposal_index"] for row in all_pairs
    }
    v3_parent_by_target = {
        row["target_proposal_index"]: row["parent_proposal_index"]
        for row in allocation["v3_target_parent_pairs"]
    }
    feature_counts = {
        name: 0
        for name in (
            "ligand_acceptor",
            "ligand_aromatic",
            "ligand_aromatic_system",
            "ligand_donor",
            "ligand_hydrophobic",
            "ligand_hydrophobic_patch",
            "ligand_negative",
            "ligand_positive",
            "ligand_shape_atom",
            "receptor_acceptor",
            "receptor_aromatic",
            "receptor_aromatic_plane",
            "receptor_donor",
            "receptor_hydrophobic",
            "receptor_hydrophobic_patch",
            "receptor_negative",
            "receptor_positive",
            "receptor_shape_atom",
        )
    }
    proposal_modes = [
        (
            evidence.PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            if index in rescue_parent_by_target
            else (
                "uniform_v3_rigid_ensemble"
                if index in v3_parent_by_target
                else ("pocket_center_baseline" if index < 8 else "uniform_fallback")
            )
        )
        for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
    ]
    baseline_modes = [
        (
            "uniform_v3_rigid_ensemble"
            if index in baseline_parent_by_target
            else ("pocket_center_baseline" if index < 8 else "uniform_fallback")
        )
        for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
    ]
    baseline_guided: dict[str, object] = {
        "schema_id": evidence.EXPECTED_BASELINE_GUIDED_PLACEMENT_SCHEMA_ID,
        "authenticated_input_receipt_sha256": authority_sha256,
        "guidance_context_sha256": guidance_context_sha256,
        "guided_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_BASE_POLICY_SHA256
        ),
        "budget_sha256": budget_sha256,
        "proposal_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "proposal_guidance_rows": [
            {
                "proposal_index": index,
                "mode": baseline_modes[index],
                "ligand_anchor_atom_indices": [],
                "receptor_anchor_atom_indices": [],
                "anchor_pairs": [],
                "anchor_pairing": None,
                "anchor_distance_aggregation": None,
                "requested_anchor_distance_angstrom_binary64_hex": None,
                "observed_anchor_distance_angstrom_binary64_hex": None,
                "ensemble_source_proposal_index": baseline_parent_by_target.get(index),
            }
            for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
        ],
        "proposal_modes": baseline_modes,
        "proposal_fingerprint_sha256s": [
            slot["proposal_fingerprint_sha256"] for slot in candidate_slots
        ],
        "guided_proposal_count": 16,
        "pocket_center_baseline_count": 8,
        "uniform_fallback_count": 40,
        "uniform_v3_ensemble_count": 16,
        "uniform_random_placement_retained_as_fallback": True,
        "feature_counts": dict(feature_counts),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    baseline_guided["receipt_sha256"] = evidence._sha256_payload(baseline_guided)
    guided: dict[str, object] = {
        "schema_id": evidence.EXPECTED_RESCUE_GUIDED_PLACEMENT_SCHEMA_ID,
        "authenticated_input_receipt_sha256": authority_sha256,
        "guidance_context_sha256": guidance_context_sha256,
        "guided_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        ),
        "budget_sha256": budget_sha256,
        "proposal_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "baseline_guided_receipt_sha256": baseline_guided["receipt_sha256"],
        "torsion_rescue_allocation_sha256": allocation["allocation_sha256"],
        "proposal_guidance_rows": [
            {
                "proposal_index": index,
                "mode": proposal_modes[index],
                "ligand_anchor_atom_indices": [],
                "receptor_anchor_atom_indices": [],
                "anchor_pairs": [],
                "anchor_pairing": None,
                "anchor_distance_aggregation": None,
                "requested_anchor_distance_angstrom_binary64_hex": None,
                "observed_anchor_distance_angstrom_binary64_hex": None,
                "ensemble_source_proposal_index": v3_parent_by_target.get(index),
                "torsion_rescue_parent_proposal_index": (
                    rescue_parent_by_target.get(index)
                ),
            }
            for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
        ],
        "proposal_modes": proposal_modes,
        "proposal_fingerprint_sha256s": [
            slot["proposal_fingerprint_sha256"] for slot in candidate_slots
        ],
        "guided_proposal_count": 16,
        "pocket_center_baseline_count": 8,
        "uniform_fallback_count": 40,
        "uniform_v3_ensemble_count": 12,
        "uniform_random_placement_retained_as_fallback": True,
        "feature_counts": dict(feature_counts),
        "source_paired_torsion_rescue_profile": True,
        "uniform_torsion_rescue_variant_count": 4,
        "uniform_torsion_rescue_variant_cap": 4,
        "proposal_objects_and_coordinates_unchanged": True,
        "selected_parent_proposal_objects_retained": True,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    guided["receipt_sha256"] = evidence._sha256_payload(guided)
    proposal: dict[str, object] = {
        "schema_id": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_SCHEMA_ID
        ),
        "authenticated_input_receipt_sha256": authority_sha256,
        "budget_sha256": budget_sha256,
        "source_ligand_system_sha256": "d" * 64,
        "source_ligand_topology_sha256": "e" * 64,
        "rescue_policy": _frozen_rescue_policy(),
        "rescue_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        ),
        "candidate_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "candidate_slots": candidate_slots,
        "baseline_guided_placement": baseline_guided,
        "guided_placement": guided,
        "proposal_objects_and_coordinates_unchanged": True,
        "selected_parent_proposal_objects_retained": True,
        "result_dependent_allocation": False,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "allocation": allocation,
    }
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
    candidates: list[dict[str, object]] = []
    expected_v3_indices = sorted(v3_parent_by_target)
    for index in range(evidence.EXPECTED_CANDIDATE_COUNT):
        rescue_parent = rescue_parent_by_target.get(index)
        v3_parent = v3_parent_by_target.get(index)
        candidate: dict[str, object] = {
            "proposal_index": index,
            # Candidate rows identify the final refined proposal. Proposal slots
            # and payload source hashes identify its pre-refinement source.
            "proposal_fingerprint_sha256": f"{index + 1000:064x}",
            "proposal_mode": proposal_modes[index],
            "ensemble_source_proposal_index": v3_parent,
            "torsion_rescue_parent_proposal_index": rescue_parent,
            "refinement_receipt_payload": {
                "source_proposal_sha256": candidate_slots[index][
                    "proposal_fingerprint_sha256"
                ],
                "pre_coordinates_sha256": candidate_slots[index][
                    "coordinate_fingerprint_sha256"
                ],
                "rotatable_child_atom_indices": [1, 3, 5, 7],
                "source_paired_parent_proposal_index": rescue_parent,
                "source_paired_torsion_rescue_pairs": rescue_pairs,
                "source_paired_torsion_rescue_allocation_sha256": allocation[
                    "allocation_sha256"
                ],
                "source_paired_torsion_rescue_guidance_context_sha256": (
                    guidance_context_sha256
                ),
                "source_paired_torsion_rescue_budget_sha256": budget_sha256,
                "v3_proposal_indices": expected_v3_indices,
                "proposal_torsion_eligibility_lane": (
                    "source_paired_torsion_rescue_variant"
                    if rescue_parent is not None
                    else (
                        "uniform_v3_rigid_ensemble"
                        if v3_parent is not None
                        else "ineligible_source_or_other_lane"
                    )
                ),
                "nested_v6_treated_proposal_as_v3_variant": v3_parent is not None,
                "rescue_target_excluded_from_nested_v3_indices": (
                    rescue_parent is not None
                ),
            },
        }
        candidates.append(candidate)
    return {"source_paired_torsion_rescue_proposal_receipt": proposal}, candidates


@pytest.mark.parametrize("drift", ("policy_profile", "variant_cap", "result_dependent"))
def test_rescue_allocation_requires_frozen_result_independent_policy(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )
    assert candidates[0]["proposal_fingerprint_sha256"] != (
        proposal["candidate_slots"][0]["proposal_fingerprint_sha256"]
    )
    rotor_count, pairs = evidence._v11_rescue_allocation(
        diagnostics,
        candidates,
        case_id="fixture",
    )
    assert rotor_count == 4
    assert [row["target_proposal_index"] for row in pairs] == [8, 13, 18, 23]

    if drift == "policy_profile":
        proposal["rescue_policy"]["policy_id"] = "result-dependent-profile"
        projection = dict(proposal["rescue_policy"])
        projection.pop("fingerprint_sha256")
        changed_policy_sha256 = evidence._sha256_payload(projection)
        proposal["rescue_policy"]["fingerprint_sha256"] = changed_policy_sha256
        proposal["rescue_policy_sha256"] = changed_policy_sha256
        allocation["rescue_policy_sha256"] = changed_policy_sha256
    elif drift == "variant_cap":
        allocation["rescue_variant_cap"] = 5
    else:
        proposal["result_dependent_allocation"] = True
        allocation["result_dependent_allocation"] = True
    allocation.pop("allocation_sha256")
    allocation["allocation_sha256"] = evidence._sha256_payload(allocation)
    proposal.pop("receipt_sha256")
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)

    with pytest.raises(ValueError):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    "field",
    ("source_proposal_sha256", "pre_coordinates_sha256"),
)
def test_rescue_allocation_binds_receipts_to_candidate_slots(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )
    evidence._v11_rescue_allocation(
        diagnostics,
        candidates,
        case_id="fixture",
    )

    candidates[0]["refinement_receipt_payload"][field] = "f" * 64
    with pytest.raises(ValueError, match="proposal slot"):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    "drift",
    (
        "allocation_count",
        "non_target_mismatch",
        "duplicate",
        "unsorted",
        "boolean",
        "negative",
    ),
)
def test_rescue_allocation_binds_rotor_authority_to_every_candidate_receipt(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    if drift == "allocation_count":
        allocation["authority_rotor_count"] = 3
    else:
        replacement = {
            "non_target_mismatch": [1, 3, 5, 9],
            "duplicate": [1, 3, 3, 7],
            "unsorted": [3, 1, 5, 7],
            "boolean": [1, 3, True, 7],
            "negative": [-1, 3, 5, 7],
        }[drift]
        candidates[0]["refinement_receipt_payload"][
            "rotatable_child_atom_indices"
        ] = replacement
    allocation.pop("allocation_sha256")
    allocation["allocation_sha256"] = evidence._sha256_payload(allocation)
    proposal.pop("receipt_sha256")
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )

    with pytest.raises(ValueError, match="rotor authority"):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    "drift",
    (
        "slot_fingerprint_duplicate",
        "candidate_v3_parent",
        "guided_v3_parent",
        "guided_inner_hash",
        "baseline_v3_parent",
        "baseline_non_target_parent",
        "baseline_non_target_mode",
    ),
)
def test_rescue_allocation_rejects_proposal_lineage_drift(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )

    if drift == "slot_fingerprint_duplicate":
        proposal["candidate_slots"][1]["proposal_fingerprint_sha256"] = proposal[
            "candidate_slots"
        ][0]["proposal_fingerprint_sha256"]
        proposal.pop("receipt_sha256")
        proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
        expected = "candidate slot"
    elif drift == "candidate_v3_parent":
        candidates[9]["ensemble_source_proposal_index"] = 0
        expected = "V3 candidate lineage"
    elif drift == "guided_v3_parent":
        proposal["guided_placement"]["proposal_guidance_rows"][9][
            "ensemble_source_proposal_index"
        ] = 0
        proposal["guided_placement"].pop("receipt_sha256")
        proposal["guided_placement"]["receipt_sha256"] = evidence._sha256_payload(
            proposal["guided_placement"]
        )
        proposal.pop("receipt_sha256")
        proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
        expected = "guided proposal lineage"
    elif drift == "guided_inner_hash":
        proposal["guided_placement"]["proposal_guidance_rows"][9][
            "ensemble_source_proposal_index"
        ] = 0
        proposal.pop("receipt_sha256")
        proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
        expected = "rescue guided placement receipt self-hash"
    else:
        baseline = proposal["baseline_guided_placement"]
        if drift == "baseline_v3_parent":
            baseline["proposal_guidance_rows"][9]["ensemble_source_proposal_index"] = 0
        elif drift == "baseline_non_target_parent":
            baseline["proposal_guidance_rows"][0]["ensemble_source_proposal_index"] = 1
        else:
            baseline["proposal_guidance_rows"][0]["mode"] = "future_fallback"
            baseline["proposal_modes"][0] = "future_fallback"
        baseline.pop("receipt_sha256")
        baseline["receipt_sha256"] = evidence._sha256_payload(baseline)
        guided = proposal["guided_placement"]
        guided["baseline_guided_receipt_sha256"] = baseline["receipt_sha256"]
        guided.pop("receipt_sha256")
        guided["receipt_sha256"] = evidence._sha256_payload(guided)
        proposal.pop("receipt_sha256")
        proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
        expected = (
            "guided proposal counts"
            if drift == "baseline_non_target_mode"
            else "baseline guided lineage"
        )

    with pytest.raises(ValueError, match=expected):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    "drift",
    (
        "allocation",
        "pairs",
        "guidance_context",
        "budget",
        "v3_indices",
        "eligibility_lane",
        "parent",
        "nested_v3",
        "rescue_excluded",
    ),
)
def test_rescue_allocation_binds_every_candidate_payload_lineage(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )
    payload = candidates[0]["refinement_receipt_payload"]
    if drift == "allocation":
        payload["source_paired_torsion_rescue_allocation_sha256"] = "f" * 64
    elif drift == "pairs":
        payload["source_paired_torsion_rescue_pairs"] = []
    elif drift == "guidance_context":
        payload["source_paired_torsion_rescue_guidance_context_sha256"] = "f" * 64
    elif drift == "budget":
        payload["source_paired_torsion_rescue_budget_sha256"] = "f" * 64
    elif drift == "v3_indices":
        payload["v3_proposal_indices"] = []
    elif drift == "eligibility_lane":
        payload["proposal_torsion_eligibility_lane"] = "uniform_v3_rigid_ensemble"
    elif drift == "parent":
        payload["source_paired_parent_proposal_index"] = 1
    elif drift == "nested_v3":
        payload["nested_v6_treated_proposal_as_v3_variant"] = True
    else:
        payload["rescue_target_excluded_from_nested_v3_indices"] = True

    with pytest.raises(ValueError, match="candidate receipt"):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    ("drift", "expected"),
    (
        ("guided_policy", "authority contract"),
        ("guided_context", "authority contract"),
        ("guided_features", "authority contract"),
        ("guided_count", "counts"),
        ("guided_row_extra", "candidate rows"),
    ),
)
def test_rescue_allocation_rejects_resealed_guidance_contract_drift(
    drift: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )
    guided = proposal["guided_placement"]
    if drift == "guided_policy":
        guided["guided_policy_sha256"] = "f" * 64
    elif drift == "guided_context":
        guided["guidance_context_sha256"] = "f" * 64
    elif drift == "guided_features":
        guided["feature_counts"]["ligand_acceptor"] = 1
    elif drift == "guided_count":
        guided["uniform_v3_ensemble_count"] += 1
    else:
        guided["proposal_guidance_rows"][0]["future_field"] = None
    guided.pop("receipt_sha256")
    guided["receipt_sha256"] = evidence._sha256_payload(guided)
    proposal.pop("receipt_sha256")
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)

    with pytest.raises(ValueError, match=expected):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    "drift",
    ("double_resealed_features", "source_ligand_system", "source_ligand_topology"),
)
def test_rescue_allocation_pins_complete_proposal_receipt(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )

    if drift == "double_resealed_features":
        baseline = proposal["baseline_guided_placement"]
        guided = proposal["guided_placement"]
        baseline["feature_counts"]["ligand_acceptor"] = 1
        guided["feature_counts"]["ligand_acceptor"] = 1
        baseline.pop("receipt_sha256")
        baseline["receipt_sha256"] = evidence._sha256_payload(baseline)
        guided["baseline_guided_receipt_sha256"] = baseline["receipt_sha256"]
        guided.pop("receipt_sha256")
        guided["receipt_sha256"] = evidence._sha256_payload(guided)
    elif drift == "source_ligand_system":
        proposal["source_ligand_system_sha256"] = "f" * 64
    else:
        proposal["source_ligand_topology_sha256"] = "f" * 64
    proposal.pop("receipt_sha256")
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)

    with pytest.raises(ValueError, match="pinned case proposal"):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ligand_anchor_atom_indices", [0]),
        ("receptor_anchor_atom_indices", [0]),
        ("anchor_pairs", [[0, 0]]),
        ("anchor_pairing", "fixture"),
        ("anchor_distance_aggregation", "fixture"),
        ("requested_anchor_distance_angstrom_binary64_hex", (1.0).hex()),
        ("observed_anchor_distance_angstrom_binary64_hex", (1.0).hex()),
    ),
)
def test_rescue_allocation_freezes_all_guidance_row_fields(
    field: str,
    value: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics, candidates = _allocation_fixture()
    proposal = diagnostics["source_paired_torsion_rescue_proposal_receipt"]
    allocation = proposal["allocation"]
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_ALLOCATION_SHA256_BY_CASE,
        "fixture",
        allocation["allocation_sha256"],
    )
    monkeypatch.setitem(
        evidence.EXPECTED_RESCUE_PROPOSAL_SHA256_BY_CASE,
        "fixture",
        proposal["receipt_sha256"],
    )
    baseline = proposal["baseline_guided_placement"]
    guided = proposal["guided_placement"]
    baseline["proposal_guidance_rows"][0][field] = value
    guided["proposal_guidance_rows"][0][field] = value
    baseline.pop("receipt_sha256")
    baseline["receipt_sha256"] = evidence._sha256_payload(baseline)
    guided["baseline_guided_receipt_sha256"] = baseline["receipt_sha256"]
    guided.pop("receipt_sha256")
    guided["receipt_sha256"] = evidence._sha256_payload(guided)
    proposal.pop("receipt_sha256")
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)

    with pytest.raises(ValueError, match="baseline guided lineage"):
        evidence._v11_rescue_allocation(
            diagnostics,
            candidates,
            case_id="fixture",
        )


def test_shared_engine_identity_requires_python_reference_in_both_lanes() -> None:
    identity = {
        "implementation_sha256": "a" * 64,
        "evaluation_pipeline_sha256": "b" * 64,
        "execution_environment_sha256": "c" * 64,
        "interaction_refiner_config_sha256": (
            evidence.EXPECTED_INTERACTION_REFINER_CONFIG_SHA256
        ),
        "scorer_backend": evidence.EXPECTED_SCORER_BACKEND,
    }
    assert evidence._shared_engine_identity(identity, identity)["scorer_backend"] == (
        evidence.EXPECTED_SCORER_BACKEND
    )

    drifted = {**identity, "scorer_backend": "rust_cpu_required"}
    with pytest.raises(ValueError, match="engine identity"):
        evidence._shared_engine_identity(identity, drifted)

    policy_config_drifted = {
        **identity,
        "interaction_refiner_config_sha256": "d" * 64,
    }
    with pytest.raises(ValueError, match="engine identity"):
        evidence._shared_engine_identity(policy_config_drifted, policy_config_drifted)


def _synthetic_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, bytes], dict[str, object], bytes, bytes, bytes, bytes]:
    report: dict[str, object] = {
        "schema_id": evidence.SCHEMA_ID,
        "operator_observed_checkout_or_base_sha1": (
            evidence.OPERATOR_OBSERVED_CHECKOUT_OR_BASE_SHA1
        ),
        "operator_observed_checkout_or_base_receipt_authenticated": False,
        "decision": "fixture",
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "primary_claim_eligible": False,
        "selection_rule_changed": False,
        "threshold_changed": False,
        "v7_replacement_authorized": False,
        "baseline": {
            "analysis": {
                "path": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE[
                    "baseline"
                ]["path"],
                "file_sha256": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE[
                    "baseline"
                ]["raw_sha256"],
                "report_sha256": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE[
                    "baseline"
                ]["report_sha256"],
            }
        },
        "rescue": {
            "analysis": {
                "path": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE["rescue"][
                    "path"
                ],
                "file_sha256": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE[
                    "rescue"
                ]["raw_sha256"],
                "report_sha256": evidence.EXPECTED_LEGACY_ANALYSIS_IDENTITY_BY_LANE[
                    "rescue"
                ]["report_sha256"],
            }
        },
    }
    report["report_sha256"] = evidence._sha256_payload(report)
    report_raw = evidence._canonical_bytes(report) + b"\n"
    source_members = {
        f".betelgeuze/fixture/member-{index:02d}.bin": str(index).encode()
        for index in range(58)
    }
    members = {**source_members, evidence.REPORT_PATH: report_raw}
    tar_raw = evidence._deterministic_tar_bytes(members)
    archive_raw = b"synthetic-zstandard-frame"
    members_raw = evidence._manifest_bytes(members)
    bundle_raw = evidence._bundle_bytes(
        evidence._sha256_bytes(archive_raw),
        evidence._sha256_bytes(members_raw),
    )
    monkeypatch.setattr(
        evidence.failure_atlas,
        "_bounded_zstd_decompress",
        lambda raw: tar_raw,
    )
    monkeypatch.setattr(evidence, "_build_report", lambda members: deepcopy(report))
    monkeypatch.setattr(
        evidence,
        "_build_superseding_non_score_verification",
        lambda members: {
            "verification_scope": "superseding_non_score_receipt_and_clearance",
            "decision": "fixture_non_score",
            "score_term_semantics_authenticated": False,
            "clearance_evaluated_candidate_count": 28,
            "legacy_analysis_status": (
                "historical_bytes_only_unavailable_for_semantic_verification"
            ),
        },
    )
    return source_members, report, report_raw, archive_raw, members_raw, bundle_raw


def _write_mode_0600(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(0o600)


def _write_current_score_term_supersession(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> bytes:
    projection = evidence._expected_score_term_supersession_projection()
    supersession_sha256 = evidence._sha256_payload(projection)
    monkeypatch.setattr(
        evidence,
        "EXPECTED_SCORE_TERM_SUPERSESSION_SHA256",
        supersession_sha256,
    )
    raw = evidence._canonical_bytes(
        {
            **projection,
            "supersession_sha256": supersession_sha256,
        }
    ) + b"\n"
    _write_mode_0600(repo_root / evidence.SCORE_TERM_SUPERSESSION_PATH, raw)
    return raw


def _pin_fixture_execution_contract(
    monkeypatch: pytest.MonkeyPatch,
    *,
    lane: str,
    case_id: str,
    result: dict[str, object],
) -> None:
    monkeypatch.setitem(
        evidence.EXPECTED_EXECUTION_CONTRACT_SHA256_BY_LANE_CASE[lane],
        case_id,
        evidence._sha256_payload(
            {
                "execution_command": result["execution_command"],
                "execution_policy": result["execution_policy"],
            }
        ),
    )
    candidates = result["engine_v2_diagnostics"]["candidates"]
    if lane == "rescue" and candidates:
        ordered_candidates = sorted(
            candidates,
            key=lambda candidate: candidate["proposal_index"],
        )
        monkeypatch.setitem(
            evidence.EXPECTED_RESCUE_CANDIDATE_PROPOSAL_FINGERPRINT_SET_SHA256_BY_CASE,
            case_id,
            evidence._sha256_payload(
                [
                    candidate["proposal_fingerprint_sha256"]
                    for candidate in ordered_candidates
                ]
            ),
        )
        ordered_receipt_sha256s = [
            candidate["refinement_receipt_sha256"]
            for candidate in ordered_candidates
        ]
        monkeypatch.setitem(
            evidence.EXPECTED_RESCUE_CANDIDATE_RECEIPT_SET_SHA256_BY_CASE,
            case_id,
            evidence._sha256_payload(ordered_receipt_sha256s),
        )


def test_frozen_summary_input_binding_and_external_boundary_are_exact() -> None:
    for lane in ("baseline", "rescue"):
        assert evidence._frozen_summary_input_binding(
            deepcopy(evidence.EXPECTED_SUMMARY_INPUT_BINDING),
            lane=lane,
        ) == evidence.EXPECTED_SUMMARY_INPUT_BINDING
        summary = {
            field: False
            for field in evidence.EXPECTED_SUMMARY_FALSE_BOUNDARY_FIELDS
        }
        evidence._frozen_summary_boundary_flags(summary, lane=lane)

        binding_drifts: list[dict[str, object]] = []
        for field, value in evidence.EXPECTED_SUMMARY_INPUT_BINDING.items():
            drifted = deepcopy(evidence.EXPECTED_SUMMARY_INPUT_BINDING)
            drifted[field] = (
                "different-mode"
                if isinstance(value, str)
                else (not value)
            )
            binding_drifts.append(drifted)
            if isinstance(value, bool):
                typed_drift = deepcopy(evidence.EXPECTED_SUMMARY_INPUT_BINDING)
                typed_drift[field] = int(value)
                binding_drifts.append(typed_drift)
        missing = deepcopy(evidence.EXPECTED_SUMMARY_INPUT_BINDING)
        missing.pop("mode")
        binding_drifts.append(missing)
        binding_drifts.append(
            {**evidence.EXPECTED_SUMMARY_INPUT_BINDING, "future_field": False}
        )
        for drifted in binding_drifts:
            with pytest.raises(ValueError, match="input binding"):
                evidence._frozen_summary_input_binding(drifted, lane=lane)

        for field in evidence.EXPECTED_SUMMARY_FALSE_BOUNDARY_FIELDS:
            for value in (True, 0):
                drifted_summary = dict(summary)
                drifted_summary[field] = value
                with pytest.raises(ValueError, match="external boundary"):
                    evidence._frozen_summary_boundary_flags(
                        drifted_summary,
                        lane=lane,
                    )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_frozen_summary_lane_identity_has_exact_complete_shape(lane: str) -> None:
    expected_fields = (
        evidence.EXPECTED_BASELINE_SUMMARY_FIELDS
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_SUMMARY_FIELDS
    )
    summary = {field: None for field in expected_fields}
    summary.update(
        {
            "engine_ids": ["engine_v2"],
            "case_count": len(evidence.EXPECTED_CASE_IDS),
            "case_ids": list(evidence.EXPECTED_CASE_IDS),
            "case_ids_sha256": evidence.EXPECTED_CASE_IDS_SHA256,
            "evidence_role": (
                "current_source_engine_v2_execution_only"
                if lane == "baseline"
                else "development_source_paired_torsion_rescue_execution_only"
            ),
            "engine_identity": deepcopy(
                evidence.EXPECTED_BASELINE_ENGINE_IDENTITY
                if lane == "baseline"
                else evidence.EXPECTED_RESCUE_ENGINE_IDENTITY
            ),
        }
    )
    if lane == "rescue":
        summary["development_source_paired_torsion_rescue"] = True
        summary["source_paired_torsion_rescue_policy"] = deepcopy(
            evidence.EXPECTED_SUMMARY_RESCUE_POLICY
        )
    evidence._frozen_summary_lane_identity(summary, lane=lane)

    drifts: list[dict[str, object]] = []
    for field, value in (
        ("engine_ids", ["engine_v1"]),
        ("evidence_role", "different-role"),
        ("case_count", float(len(evidence.EXPECTED_CASE_IDS))),
        ("case_ids", dict.fromkeys(evidence.EXPECTED_CASE_IDS)),
    ):
        drifted = deepcopy(summary)
        drifted[field] = value
        drifts.append(drifted)
    engine_drift = deepcopy(summary)
    engine_drift["engine_identity"]["stage0_eligible"] = 0
    drifts.append(engine_drift)
    missing = deepcopy(summary)
    missing.pop("profiles")
    drifts.append(missing)
    drifts.append({**deepcopy(summary), "future_field": None})
    if lane == "baseline":
        drifts.append(
            {
                **deepcopy(summary),
                "source_paired_torsion_rescue_policy": deepcopy(
                    evidence.EXPECTED_SUMMARY_RESCUE_POLICY
                ),
            }
        )
    else:
        policy_drift = deepcopy(summary)
        policy_drift["source_paired_torsion_rescue_policy"][
            "result_dependent_allocation"
        ] = True
        drifts.append(policy_drift)
        rescue_flag_drift = deepcopy(summary)
        rescue_flag_drift["development_source_paired_torsion_rescue"] = 1
        drifts.append(rescue_flag_drift)
    for drifted in drifts:
        with pytest.raises(ValueError):
            evidence._frozen_summary_lane_identity(drifted, lane=lane)


def test_frozen_profiles_pin_every_retained_profile_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profiles = [
        {
            "case_id": case_id,
            "heavy_atom_count": index + 1,
            "rotor_count": index,
            "ring_count": index % 3,
            "ligand_artifact_sha256": f"{index + 1:064x}",
            "profile_method_id": "fixture-profile/1.0.0",
            "ring_profile_method_id": "fixture-ring/1.0.0",
            "size_subgroup": "fixture-size",
            "rotor_subgroup": "fixture-rotor",
            "ring_subgroup": "fixture-ring",
        }
        for index, case_id in enumerate(evidence.EXPECTED_CASE_IDS)
    ]
    monkeypatch.setattr(
        evidence,
        "EXPECTED_PROFILE_SET_SHA256",
        evidence._sha256_payload(profiles),
    )
    for lane in ("baseline", "rescue"):
        assert evidence._frozen_profiles(deepcopy(profiles), lane=lane) == tuple(
            profiles
        )
        for profile in profiles:
            evidence._bind_frozen_profile_to_result(
                profile,
                {"native_artifact_sha256": profile["ligand_artifact_sha256"]},
                lane=lane,
                case_id=profile["case_id"],
            )

    for field in evidence.EXPECTED_PROFILE_FIELDS:
        drifted = deepcopy(profiles)
        original = drifted[0][field]
        drifted[0][field] = original + 1 if isinstance(original, int) else f"{original}-x"
        with pytest.raises(ValueError):
            evidence._frozen_profiles(drifted, lane="rescue")
    missing = deepcopy(profiles)
    missing[0].pop("ring_subgroup")
    with pytest.raises(ValueError, match="profile projection"):
        evidence._frozen_profiles(missing, lane="baseline")
    extra = deepcopy(profiles)
    extra[0]["future_field"] = None
    with pytest.raises(ValueError, match="profile projection"):
        evidence._frozen_profiles(extra, lane="rescue")
    with pytest.raises(ValueError, match="profile native input"):
        evidence._bind_frozen_profile_to_result(
            profiles[0],
            {"native_artifact_sha256": "f" * 64},
            lane="rescue",
            case_id=profiles[0]["case_id"],
        )


def _preparation_failure_frozen_result(lane: str) -> dict[str, object]:
    diagnostic_fields = (
        evidence.EXPECTED_BASELINE_DIAGNOSTIC_FIELDS
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_DIAGNOSTIC_FIELDS
    )
    diagnostic_schema = (
        evidence.EXPECTED_BASELINE_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    diagnostics = {field: None for field in diagnostic_fields}
    diagnostics.update(
        {
            "schema_id": diagnostic_schema,
            "preparation_status": "failure",
            "preparation_failure_code": evidence.EXPECTED_PREPARATION_FAILURE_CODE,
            "candidate_budget": evidence.EXPECTED_CANDIDATE_COUNT,
            "candidates": [],
            "diagnostic_evaluation_seconds": 0.0,
            "diagnostic_evaluation_excluded_from_runtime": True,
        }
    )
    diagnostics.update(
        {
            field: 0
            for field in (
                evidence.EXPECTED_PREPARATION_FAILURE_ZERO_INT_DIAGNOSTIC_FIELDS
            )
        }
    )
    diagnostics.update(
        {
            field: False
            for field in (
                evidence.EXPECTED_PREPARATION_FAILURE_FALSE_DIAGNOSTIC_FIELDS
            )
        }
    )
    result = {field: None for field in evidence.EXPECTED_RESULT_FIELDS}
    result.update(
        {
            "case_id": evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
            "engine_id": "engine_v2",
            "status": "failure",
            "runtime_seconds": 1.0,
            "receptor_artifact_sha256": "a" * 64,
            "reference_artifact_sha256": "b" * 64,
            "native_artifact_sha256": "c" * 64,
            "seed_artifact_sha256": "d" * 64,
            "execution_command": ["historical-runner"],
            "execution_policy": [
                f'scorer_backend="{evidence.EXPECTED_SCORER_BACKEND}"'
            ],
            "rmsd_angstroms": [],
            "geometric_valid": [],
            "chemical_valid": [],
            "pose_artifact_sha256s": [],
            "failure_code": "engine_v2_case_failed",
            "engine_v2_diagnostics": diagnostics,
        }
    )
    return result


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_frozen_result_parser_is_live_schema_independent(
    lane: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _preparation_failure_frozen_result(lane)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane=lane,
        case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        result=result,
    )

    assert (
        evidence._historical_v11_result(
            result,
            lane=lane,
            case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        )
        == result
    )

    failure_reason_drift = deepcopy(result)
    failure_reason_drift["engine_v2_diagnostics"]["preparation_failure_code"] = (
        "different_failure_reason"
    )
    with pytest.raises(ValueError, match="preparation failure"):
        evidence._historical_v11_result(
            failure_reason_drift,
            lane=lane,
            case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        )

    drifted = {**result, "future_live_field": "must-not-be-accepted"}
    with pytest.raises(ValueError, match="result shape"):
        evidence._historical_v11_result(
            drifted,
            lane=lane,
            case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_preparation_failure_diagnostics_require_exact_frozen_values(
    lane: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _preparation_failure_frozen_result(lane)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane=lane,
        case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        result=result,
    )

    drifts: list[tuple[str, object]] = [
        *[
            (field, 1)
            for field in (
                evidence.EXPECTED_PREPARATION_FAILURE_ZERO_INT_DIAGNOSTIC_FIELDS
            )
        ],
        ("candidate_success_count", False),
        ("receptor_atom_count", 0.0),
        *[
            (field, True)
            for field in (
                evidence.EXPECTED_PREPARATION_FAILURE_FALSE_DIAGNOSTIC_FIELDS
            )
        ],
        ("receptor_ion_proxy_used", 0),
        ("diagnostic_evaluation_excluded_from_runtime", False),
        ("diagnostic_evaluation_excluded_from_runtime", 1),
        ("diagnostic_evaluation_seconds", 1.0),
        ("diagnostic_evaluation_seconds", 0),
        ("diagnostic_evaluation_seconds", -0.0),
        ("candidate_budget", float(evidence.EXPECTED_CANDIDATE_COUNT)),
        ("proposal_oracle_rmsd_angstrom", 0.0),
        ("scorer_backend_receipt", {}),
    ]
    if lane == "rescue":
        drifts.append(("source_paired_torsion_rescue_proposal_receipt", {}))

    for field, value in drifts:
        drifted = deepcopy(result)
        drifted["engine_v2_diagnostics"][field] = value
        with pytest.raises(ValueError):
            evidence._historical_v11_result(
                drifted,
                lane=lane,
                case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
            )


def _seal_receipt(payload: dict[str, object]) -> str:
    projection = dict(payload)
    projection.pop("receipt_sha256", None)
    receipt_sha256 = evidence._sha256_payload(projection)
    payload["receipt_sha256"] = receipt_sha256
    return receipt_sha256


def _successful_frozen_result(
    lane: str,
    *,
    case_id: str = "5SD5_HWI",
) -> dict[str, object]:
    candidate_fields = (
        evidence.EXPECTED_BASELINE_CANDIDATE_FIELDS
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_CANDIDATE_FIELDS
    )
    candidate_schema = (
        evidence.EXPECTED_BASELINE_CANDIDATE_SCHEMA_ID
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_CANDIDATE_SCHEMA_ID
    )
    candidates: list[dict[str, object]] = []
    for index in range(evidence.EXPECTED_CANDIDATE_COUNT):
        payload: dict[str, object]
        if lane == "baseline":
            payload = {}
            receipt_sha256 = f"{index + 300:064x}"
        else:
            payload = {field: None for field in evidence.EXPECTED_V11_RECEIPT_FIELDS}
            payload.update(
                {
                    "schema_id": evidence.EXPECTED_RECEIPT_SCHEMA_ID,
                    "development_only": True,
                    "claim_safe": False,
                    "fresh_execution_authorized": False,
                    "scientifically_validated": False,
                    "stage0_eligible": False,
                    "source_paired_torsion_rescue_profile": True,
                    "source_paired_torsion_rescue_policy_sha256": (
                        evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
                    ),
                    "source_paired_torsion_rescue_variant_cap": (
                        evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_VARIANT_CAP
                    ),
                    "result_dependent_eligibility": False,
                    "config_sha256": (
                        evidence.EXPECTED_SOURCE_PAIRED_REFINER_COMPOSITE_CONFIG_SHA256_BY_CASE[
                            case_id
                        ]
                    ),
                    "clearance_measurement_evaluated": False,
                    "clearance_measurement_unavailable_reason": (
                        "not_source_paired_rescue_target"
                    ),
                    "clearance_radii_policy_sha256": "",
                    "clearance_ligand_atom_count": 0,
                    "clearance_receptor_atom_count": 0,
                    "clearance_full_cartesian_pair_count": 0,
                    "clearance_pair_count_bound": (
                        evidence.EXPECTED_CLEARANCE_PAIR_COUNT_BOUND
                    ),
                    "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
                    "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
                    "optimized_coordinates_sha256": "",
                }
            )
            receipt_sha256 = _seal_receipt(payload)
        candidate = {field: None for field in candidate_fields}
        score_terms = {
            name: (0.0).hex() for name in evidence.EXPECTED_SCORER_TERM_NAMES
        }
        score_terms["typed_vdw"] = float(index).hex()
        score_terms["total_score"] = float(index).hex()
        candidate.update(
            {
                "schema_id": candidate_schema,
                "proposal_index": index,
                "proposal_mode": "uniform_fallback",
                "status": "success",
                "error_code": "",
                "score": float(index),
                "rmsd_angstrom": float(index + 10),
                "geometric_valid": True,
                "chemical_valid": True,
                "selection_eligible": False,
                "posebusters_failed_check_ids": [],
                "proposal_fingerprint_sha256": f"{index + 1:064x}",
                "coordinate_fingerprint_sha256": f"{index + 65:064x}",
                "pose_artifact_sha256": f"{index + 129:064x}",
                "score_terms_receipt_sha256": f"{index + 193:064x}",
                "score_term_binary64_hex": score_terms,
                "hbond_count": 0,
                "ensemble_source_proposal_index": None,
                "refinement_original_pose_valid": True,
                "refinement_accepted_steps": 0,
                "refinement_accepted_rotation_steps": 0,
                "refinement_initial_penalty_binary64_hex": (0.0).hex(),
                "refinement_final_penalty_binary64_hex": (0.0).hex(),
                "refinement_total_translation_binary64_hex": [
                    (0.0).hex(),
                    (0.0).hex(),
                    (0.0).hex(),
                ],
                "refinement_total_rotation_vector_binary64_hex": [
                    (0.0).hex(),
                    (0.0).hex(),
                    (0.0).hex(),
                ],
                "refinement_receipt_sha256": receipt_sha256,
                "refinement_receipt_payload": payload,
            }
        )
        if lane == "rescue":
            candidate["torsion_rescue_parent_proposal_index"] = None
            payload.update(
                {
                    "legacy_v7_receipt_schema_id": (
                        "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
                    ),
                    "source_lane_retained": True,
                    "ranking_score_reused_as_physical_energy": False,
                    "posebusters_or_rmsd_used_for_selection": False,
                    "accepted_rotation_steps_include_torsion": True,
                    "generic_penalty_scope": (
                        "source_proposal_to_final_coordinates_v7_objective"
                    ),
                    "baseline_v6_penalty_scope": ("post_v6_coordinates_v7_objective"),
                    "source_proposal_sha256": f"{index + 500:064x}",
                    "pre_coordinates_sha256": candidate[
                        "coordinate_fingerprint_sha256"
                    ],
                    "v3_proposal_indices": [],
                    "torsion_selected": False,
                    "accepted_torsion_steps": 0,
                    "torsion_trial_objective_evaluation_count": 0,
                    "accepted_translation_steps": 0,
                    "accepted_rigid_rotation_steps": 0,
                    "fallback_direction_step_count": 0,
                    "line_search_evaluation_count": 0,
                    "baseline_coordinates_sha256": candidate[
                        "coordinate_fingerprint_sha256"
                    ],
                    "post_coordinates_sha256": candidate[
                        "coordinate_fingerprint_sha256"
                    ],
                    "initial_penalty_binary64_hex": candidate[
                        "refinement_initial_penalty_binary64_hex"
                    ],
                    "final_penalty_binary64_hex": candidate[
                        "refinement_final_penalty_binary64_hex"
                    ],
                    "accepted_steps": candidate["refinement_accepted_steps"],
                    "accepted_rotation_steps": candidate[
                        "refinement_accepted_rotation_steps"
                    ],
                    "original_pose_valid": candidate["refinement_original_pose_valid"],
                    "total_translation_binary64_hex": candidate[
                        "refinement_total_translation_binary64_hex"
                    ],
                    "total_rotation_vector_binary64_hex": candidate[
                        "refinement_total_rotation_vector_binary64_hex"
                    ],
                }
            )
            baseline_v6_payload = {
                "schema_id": evidence.EXPECTED_BASELINE_V6_RECEIPT_SCHEMA_ID,
                "source_proposal_sha256": payload["source_proposal_sha256"],
                "config_sha256": (
                    evidence.EXPECTED_BASELINE_V6_COMPOSITE_CONFIG_SHA256_BY_CASE[
                        case_id
                    ]
                ),
                "lane": "translation_v2",
                "v3_proposal_indices": [],
                "nested_refiner_id": "fixture-v2",
                "nested_refiner_version": "1.0.0",
                "nested_receipt_sha256": f"{index + 400:064x}",
                "initial_penalty_binary64_hex": (0.0).hex(),
                "final_penalty_binary64_hex": (0.0).hex(),
                "accepted_steps": 0,
                "accepted_translation_steps": 0,
                "accepted_rotation_steps": 0,
                "fallback_direction_step_count": 0,
                "line_search_evaluation_count": 0,
                "original_pose_valid": True,
                "pre_coordinates_sha256": payload["pre_coordinates_sha256"],
                "post_coordinates_sha256": payload["baseline_coordinates_sha256"],
                "total_translation_binary64_hex": payload[
                    "total_translation_binary64_hex"
                ],
                "total_rotation_vector_binary64_hex": payload[
                    "total_rotation_vector_binary64_hex"
                ],
                "ranking_score_reused_as_physical_energy": False,
                "source_lane_retained": True,
                "scientifically_validated": False,
            }
            baseline_v6_sha256 = _seal_receipt(baseline_v6_payload)
            payload["baseline_v6_receipt_payload"] = baseline_v6_payload
            payload["baseline_v6_receipt_sha256"] = baseline_v6_sha256
            candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
        candidates.append(candidate)
    diagnostic_fields = (
        evidence.EXPECTED_BASELINE_DIAGNOSTIC_FIELDS
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_DIAGNOSTIC_FIELDS
    )
    diagnostic_schema = (
        evidence.EXPECTED_BASELINE_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else evidence.EXPECTED_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    diagnostics = {field: None for field in diagnostic_fields}
    diagnostics.update(
        {
            "schema_id": diagnostic_schema,
            "preparation_status": "success",
            "preparation_failure_code": "",
            "candidate_budget": evidence.EXPECTED_CANDIDATE_COUNT,
            "candidate_success_count": evidence.EXPECTED_CANDIDATE_COUNT,
            "candidate_failure_count": 0,
            "candidates": candidates,
            "ligand_atom_count": 20,
            "receptor_atom_count": 100,
            "ligand_partial_charge_count": 20,
            "receptor_partial_charge_count": 100,
            "receptor_donor_count": 0,
            "receptor_acceptor_count": 2,
            "ligand_donor_count": 1,
            "ligand_acceptor_count": 1,
            "receptor_ion_proxy_count": 0,
            "diagnostic_evaluation_seconds": 0.5,
            "diagnostic_evaluation_excluded_from_runtime": True,
            "charge_coverage_complete": True,
            "hbond_feature_covered": True,
            "receptor_ion_proxy_used": False,
            "receptor_ion_coordination_modeled": False,
            "ligand_metal_support": False,
            "proposal_oracle_rmsd_angstrom": 10.0,
            "scorer_backend_receipt": deepcopy(
                evidence.EXPECTED_SCORER_BACKEND_RECEIPT
            ),
        }
    )
    if lane == "rescue":
        diagnostics["source_paired_torsion_rescue_proposal_receipt"] = {}
    ranked = candidates[:5]
    result = {field: None for field in evidence.EXPECTED_RESULT_FIELDS}
    result.update(
        {
            "case_id": case_id,
            "engine_id": "engine_v2",
            "status": "success",
            "runtime_seconds": 1.0,
            "receptor_artifact_sha256": "a" * 64,
            "reference_artifact_sha256": "b" * 64,
            "native_artifact_sha256": "c" * 64,
            "seed_artifact_sha256": "d" * 64,
            "execution_command": ["historical-runner"],
            "execution_policy": [
                f'scorer_backend="{evidence.EXPECTED_SCORER_BACKEND}"'
            ],
            "rmsd_angstroms": [candidate["rmsd_angstrom"] for candidate in ranked],
            "geometric_valid": [True] * 5,
            "chemical_valid": [True] * 5,
            "pose_artifact_sha256s": [
                candidate["pose_artifact_sha256"] for candidate in ranked
            ],
            "failure_code": "",
            "engine_v2_diagnostics": diagnostics,
        }
    )
    return result


def test_frozen_result_parser_accepts_successful_baseline_and_rescue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for lane in ("baseline", "rescue"):
        result = _successful_frozen_result(lane)
        if lane == "rescue":
            first_candidate = result["engine_v2_diagnostics"]["candidates"][0]
            assert first_candidate["proposal_fingerprint_sha256"] != (
                first_candidate["refinement_receipt_payload"][
                    "source_proposal_sha256"
                ]
            )
        _pin_fixture_execution_contract(
            monkeypatch,
            lane=lane,
            case_id="5SD5_HWI",
            result=result,
        )
        assert (
            evidence._historical_v11_result(
                result,
                lane=lane,
                case_id="5SD5_HWI",
            )
            == result
        )


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_successful_diagnostics_require_frozen_typed_and_derived_contract(
    lane: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result(lane)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane=lane,
        case_id="5SD5_HWI",
        result=result,
    )
    drifts: list[tuple[str, object]] = [
        ("candidate_success_count", False),
        ("candidate_failure_count", 0.0),
        ("receptor_atom_count", 0),
        ("ligand_atom_count", 0),
        ("receptor_partial_charge_count", 99),
        ("ligand_partial_charge_count", 19),
        ("receptor_donor_count", -1),
        ("receptor_acceptor_count", 2.0),
        ("receptor_ion_proxy_count", 101),
        ("diagnostic_evaluation_seconds", 0),
        ("diagnostic_evaluation_seconds", -1.0),
        ("diagnostic_evaluation_seconds", float("nan")),
        ("diagnostic_evaluation_seconds", float("inf")),
        ("diagnostic_evaluation_excluded_from_runtime", False),
        ("diagnostic_evaluation_excluded_from_runtime", 1),
        ("charge_coverage_complete", False),
        ("charge_coverage_complete", 1),
        ("hbond_feature_covered", False),
        ("hbond_feature_covered", 1),
        ("receptor_ion_proxy_used", True),
        ("receptor_ion_proxy_used", 0),
        ("receptor_ion_coordination_modeled", True),
        ("receptor_ion_coordination_modeled", 0),
        ("ligand_metal_support", True),
        ("ligand_metal_support", 0),
        ("proposal_oracle_rmsd_angstrom", None),
        ("proposal_oracle_rmsd_angstrom", 10),
        ("proposal_oracle_rmsd_angstrom", 11.0),
    ]
    if lane == "rescue":
        drifts.append(("source_paired_torsion_rescue_proposal_receipt", None))
    for field, value in drifts:
        drifted = deepcopy(result)
        drifted["engine_v2_diagnostics"][field] = value
        with pytest.raises(ValueError):
            evidence._historical_v11_result(
                drifted,
                lane=lane,
                case_id="5SD5_HWI",
            )

    positive_ion = deepcopy(result)
    positive_ion["engine_v2_diagnostics"]["receptor_ion_proxy_count"] = 1
    positive_ion["engine_v2_diagnostics"]["receptor_ion_proxy_used"] = True
    assert evidence._historical_v11_result(
        positive_ion,
        lane=lane,
        case_id="5SD5_HWI",
    ) == positive_ion

    no_hbond_coverage = deepcopy(result)
    no_hbond_diagnostics = no_hbond_coverage["engine_v2_diagnostics"]
    no_hbond_diagnostics["receptor_acceptor_count"] = 0
    no_hbond_diagnostics["ligand_donor_count"] = 0
    no_hbond_diagnostics["ligand_acceptor_count"] = 0
    no_hbond_diagnostics["hbond_feature_covered"] = False
    assert evidence._historical_v11_result(
        no_hbond_coverage,
        lane=lane,
        case_id="5SD5_HWI",
    ) == no_hbond_coverage


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_successful_results_treat_score_term_projection_as_opaque_legacy_bytes(
    lane: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result(lane)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane=lane,
        case_id="5SD5_HWI",
        result=result,
    )

    opaque_legacy_drift = deepcopy(result)
    candidate = opaque_legacy_drift["engine_v2_diagnostics"]["candidates"][0]
    candidate[
        "score_terms_receipt_sha256"
    ] = "f" * 64
    candidate["score_term_binary64_hex"]["weak_pocket_prior"] = "opaque-legacy"
    assert evidence._historical_v11_result(
        opaque_legacy_drift,
        lane=lane,
        case_id="5SD5_HWI",
    ) == opaque_legacy_drift


@pytest.mark.parametrize("lane", ("baseline", "rescue"))
def test_superseding_result_projection_never_consumes_legacy_score_fields(
    lane: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result(lane)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane=lane,
        case_id="5SD5_HWI",
        result=result,
    )
    drifted = deepcopy(result)
    candidate = drifted["engine_v2_diagnostics"]["candidates"][0]
    candidate["score"] = {"opaque": "legacy"}
    candidate["score_terms_receipt_sha256"] = 17
    candidate["score_term_binary64_hex"] = ["not", "a", "term", "vector"]
    candidate["hbond_count"] = False
    for field in evidence.LEGACY_UNAUTHENTICATED_SCORE_RANKED_RESULT_FIELDS:
        drifted[field] = {"opaque": field}

    def fail_ranked_projection(*args: object, **kwargs: object) -> None:
        raise AssertionError("ranked projection must not run")

    monkeypatch.setattr(
        evidence.failure_atlas,
        "_validate_ranked_result_projection",
        fail_ranked_projection,
    )
    observed = evidence._historical_v11_result(
        drifted,
        lane=lane,
        case_id="5SD5_HWI",
        verify_legacy_score_projection=False,
    )

    assert not (
        set(observed) & evidence.LEGACY_UNAUTHENTICATED_SCORE_RANKED_RESULT_FIELDS
    )
    observed_candidate = observed["engine_v2_diagnostics"]["candidates"][0]
    assert not (
        set(observed_candidate)
        & evidence.LEGACY_UNAUTHENTICATED_CANDIDATE_SCORE_FIELDS
    )
    non_score_drift = deepcopy(drifted)
    non_score_drift["engine_v2_diagnostics"]["candidates"][0][
        "rmsd_angstrom"
    ] = 99.0
    assert evidence._non_score_result_projection(drifted) != (
        evidence._non_score_result_projection(non_score_drift)
    )


@pytest.mark.parametrize("case_id", ("5SD5_HWI", "5SIS_JSM"))
def test_frozen_rescue_accepts_distinct_pinned_case_composite_configs(
    case_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result("rescue", case_id=case_id)
    _pin_fixture_execution_contract(
        monkeypatch,
        lane="rescue",
        case_id=case_id,
        result=result,
    )

    assert (
        evidence._historical_v11_result(
            result,
            lane="rescue",
            case_id=case_id,
        )
        == result
    )


@pytest.mark.parametrize(
    "drift",
    (
        "proposal_mode",
        "ensemble_lineage",
        "posebusters_flags",
        "rescue_profile",
        "rescue_policy",
        "rescue_variant_cap",
        "result_dependent_eligibility",
        "refiner_config",
        "generic_refiner_config",
        "nested_v6_stale_hash",
        "nested_v6_outer_link",
        "nested_v6_config",
        "nested_v6_projection",
        "nested_v6_counter",
        "nested_v6_keyset",
        "proposal_fingerprint_duplicate",
        "scorer_backend_receipt",
        "execution_scorer_backend",
        "execution_command",
        "execution_policy",
        "post_coordinates",
        "unselected_baseline_coordinates",
        "refinement_projection",
        "v1_schema",
        "v11_keyset",
    ),
)
def test_successful_frozen_rescue_rejects_resealed_contract_drift(
    drift: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result("rescue")
    _pin_fixture_execution_contract(
        monkeypatch,
        lane="rescue",
        case_id="5SD5_HWI",
        result=result,
    )
    candidate = result["engine_v2_diagnostics"]["candidates"][0]
    payload = candidate["refinement_receipt_payload"]
    nested_v6 = payload["baseline_v6_receipt_payload"]

    def reseal_nested_v6() -> None:
        nested_sha256 = _seal_receipt(nested_v6)
        payload["baseline_v6_receipt_sha256"] = nested_sha256
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)

    if drift == "proposal_mode":
        candidate["proposal_mode"] = "future_unknown_mode"
    elif drift == "ensemble_lineage":
        candidate["ensemble_source_proposal_index"] = 1
    elif drift == "posebusters_flags":
        candidate["geometric_valid"] = False
    elif drift == "rescue_profile":
        payload["source_paired_torsion_rescue_profile"] = False
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "rescue_policy":
        payload["source_paired_torsion_rescue_policy_sha256"] = "f" * 64
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "rescue_variant_cap":
        payload["source_paired_torsion_rescue_variant_cap"] = 5
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "result_dependent_eligibility":
        payload["result_dependent_eligibility"] = True
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "refiner_config":
        payload["config_sha256"] = "f" * 64
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "generic_refiner_config":
        payload["config_sha256"] = evidence.EXPECTED_INTERACTION_REFINER_CONFIG_SHA256
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "nested_v6_stale_hash":
        nested_v6["accepted_steps"] = 1
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "nested_v6_outer_link":
        payload["baseline_v6_receipt_sha256"] = "f" * 64
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "nested_v6_config":
        nested_v6["config_sha256"] = "f" * 64
        reseal_nested_v6()
    elif drift == "nested_v6_projection":
        nested_v6["original_pose_valid"] = False
        reseal_nested_v6()
    elif drift == "nested_v6_counter":
        payload["torsion_trial_objective_evaluation_count"] = 1
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "nested_v6_keyset":
        nested_v6["future_field"] = None
        reseal_nested_v6()
    elif drift == "proposal_fingerprint_duplicate":
        result["engine_v2_diagnostics"]["candidates"][1][
            "proposal_fingerprint_sha256"
        ] = candidate["proposal_fingerprint_sha256"]
    elif drift == "scorer_backend_receipt":
        result["engine_v2_diagnostics"]["scorer_backend_receipt"]["backend"] = (
            "rust_cpu_required"
        )
    elif drift == "execution_scorer_backend":
        result["execution_policy"] = ['scorer_backend="rust_cpu_required"']
    elif drift == "execution_command":
        result["execution_command"].append("--different-seed")
    elif drift == "execution_policy":
        result["execution_policy"].append("timeout_seconds=301")
    elif drift == "post_coordinates":
        payload["post_coordinates_sha256"] = "f" * 64
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "unselected_baseline_coordinates":
        payload["baseline_coordinates_sha256"] = "e" * 64
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "refinement_projection":
        payload["final_penalty_binary64_hex"] = (1.0).hex()
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    elif drift == "v1_schema":
        payload["schema_id"] = (
            "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0"
        )
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)
    else:
        payload.pop("clearance_pair_count_bound")
        candidate["refinement_receipt_sha256"] = _seal_receipt(payload)

    with pytest.raises(ValueError):
        evidence._historical_v11_result(
            result,
            lane="rescue",
            case_id="5SD5_HWI",
        )


def test_frozen_rescue_pins_complete_candidate_receipt_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result("rescue")
    _pin_fixture_execution_contract(
        monkeypatch,
        lane="rescue",
        case_id="5SD5_HWI",
        result=result,
    )
    candidate = result["engine_v2_diagnostics"]["candidates"][0]
    payload = candidate["refinement_receipt_payload"]
    nested_v6 = payload["baseline_v6_receipt_payload"]
    nested_v6["lane"] = "self_consistent_resealed_drift"
    payload["baseline_v6_receipt_sha256"] = _seal_receipt(nested_v6)
    candidate["refinement_receipt_sha256"] = _seal_receipt(payload)

    with pytest.raises(ValueError, match="candidate receipt set"):
        evidence._historical_v11_result(
            result,
            lane="rescue",
            case_id="5SD5_HWI",
        )


def test_frozen_rescue_pins_final_candidate_proposal_fingerprint_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _successful_frozen_result("rescue")
    _pin_fixture_execution_contract(
        monkeypatch,
        lane="rescue",
        case_id="5SD5_HWI",
        result=result,
    )
    result["engine_v2_diagnostics"]["candidates"][0][
        "proposal_fingerprint_sha256"
    ] = "f" * 64

    with pytest.raises(ValueError, match="candidate proposal fingerprint set"):
        evidence._historical_v11_result(
            result,
            lane="rescue",
            case_id="5SD5_HWI",
        )


def test_pose_member_binds_exact_ranked_sdf_record_hashes() -> None:
    records = tuple(f"pose-{index}\n$$$$\n".encode("ascii") for index in range(5))
    path = ".betelgeuze/fixture/poses/case.sdf"
    expected = [evidence._sha256_bytes(record) for record in records]
    members = {path: b"".join(records)}

    evidence._validate_pose_member(
        members,
        path,
        expected,
        lane="fixture",
        case_id="fixture",
    )

    members[path] = b"".join((*records[:2], records[3], records[2], records[4]))
    with pytest.raises(ValueError, match="contradict retained SDF"):
        evidence._validate_pose_member(
            members,
            path,
            expected,
            lane="fixture",
            case_id="fixture",
        )


def test_source_reader_rejects_mode_symlink_and_aggregate_size_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    member = repo_root / ".betelgeuze/state/member.bin"
    _write_mode_0600(member, b"member")
    assert evidence._read_regular_mode_0600(member, repo_root=repo_root)[1] == b"member"

    member.chmod(0o644)
    with pytest.raises(ValueError, match="bounded regular-file contract"):
        evidence._read_regular_mode_0600(member, repo_root=repo_root)
    member.chmod(0o600)
    symlink = repo_root / ".betelgeuze/state/link.bin"
    symlink.symlink_to(member)
    with pytest.raises(ValueError, match="opened safely"):
        evidence._read_regular_mode_0600(symlink, repo_root=repo_root)

    run_root = repo_root / ".betelgeuze/run"
    run_root.mkdir(mode=0o700)
    _write_mode_0600(run_root / "first.bin", b"aa")
    _write_mode_0600(run_root / "second.bin", b"bb")
    with pytest.raises(ValueError, match="aggregate size bound"):
        evidence._collect_run_root(
            repo_root,
            ".betelgeuze/run",
            maximum_total_bytes=3,
        )


def test_bundle_verifier_rejects_fixed_pin_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report, _, archive_raw, members_raw, bundle_raw = _synthetic_bundle(monkeypatch)
    report_sha256 = str(report["report_sha256"])
    expected = {
        "expected_archive_sha256": evidence._sha256_bytes(archive_raw),
        "expected_members_sha256": evidence._sha256_bytes(members_raw),
        "expected_bundle_sha256": evidence._sha256_bytes(bundle_raw),
        "expected_report_sha256": report_sha256,
    }

    observed, identity = evidence._verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        verification_scope="legacy_pack",
        **expected,
    )

    assert observed == report
    assert identity["report_sha256"] == report_sha256
    with pytest.raises(ValueError, match="archive bundle identity"):
        evidence._verify_bundle_bytes(
            archive_raw=archive_raw,
            members_raw=members_raw,
            bundle_raw=bundle_raw,
            verification_scope="legacy_pack",
            **{**expected, "expected_archive_sha256": "0" * 64},
        )


def test_superseding_bundle_verifier_does_not_rebuild_legacy_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report, _, archive_raw, members_raw, bundle_raw = _synthetic_bundle(monkeypatch)

    def fail_legacy_rebuild(*args: object, **kwargs: object) -> None:
        raise AssertionError("legacy report rebuild must not run")

    monkeypatch.setattr(evidence, "_build_report", fail_legacy_rebuild)
    observed, identity = evidence._verify_bundle_bytes(
        archive_raw=archive_raw,
        members_raw=members_raw,
        bundle_raw=bundle_raw,
        expected_archive_sha256=evidence._sha256_bytes(archive_raw),
        expected_members_sha256=evidence._sha256_bytes(members_raw),
        expected_bundle_sha256=evidence._sha256_bytes(bundle_raw),
        expected_report_sha256=str(report["report_sha256"]),
        verification_scope="superseding_non_score",
    )

    assert observed == report
    assert identity["verification_scope"] == "superseding_non_score"
    assert identity["superseding_verification"][
        "score_term_semantics_authenticated"
    ] is False


def test_pinned_verifier_requires_matching_external_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, report, report_raw, archive_raw, members_raw, bundle_raw = _synthetic_bundle(
        monkeypatch
    )
    pins = {
        "EXPECTED_EVIDENCE_ARCHIVE_SHA256": evidence._sha256_bytes(archive_raw),
        "EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256": evidence._sha256_bytes(members_raw),
        "EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256": evidence._sha256_bytes(bundle_raw),
        "EXPECTED_REPORT_SHA256": str(report["report_sha256"]),
    }
    for name, value in pins.items():
        monkeypatch.setattr(evidence, name, value)
    supersession_projection = evidence._expected_score_term_supersession_projection()
    supersession_sha256 = evidence._sha256_payload(supersession_projection)
    monkeypatch.setattr(
        evidence,
        "EXPECTED_SCORE_TERM_SUPERSESSION_SHA256",
        supersession_sha256,
    )
    supersession_raw = evidence._canonical_bytes(
        {
            **supersession_projection,
            "supersession_sha256": supersession_sha256,
        }
    ) + b"\n"
    for relative, raw in (
        (evidence.ARCHIVE_PATH, archive_raw),
        (evidence.MEMBERS_PATH, members_raw),
        (evidence.BUNDLE_PATH, bundle_raw),
        (evidence.REPORT_PATH, report_raw),
        (evidence.SCORE_TERM_SUPERSESSION_PATH, supersession_raw),
    ):
        _write_mode_0600(tmp_path / relative, raw)

    observed, identity = evidence.verify_pinned_evidence(tmp_path)

    assert observed == report
    assert identity["development_only"] is True
    for field in (
        "claim_safe",
        "complete_scorer_term_receipts_retained",
        "contains_fresh_internal_blind_holdout",
        "fresh_execution_authorized",
        "primary_claim_eligible",
        "product_promotion_eligible",
        "public_claim_eligible",
        "reconstruction_available",
        "scientifically_validated",
        "score_term_semantics_authenticated",
        "selection_rule_changed",
        "stage0_eligible",
        "threshold_changed",
        "v7_replacement_authorized",
    ):
        assert identity[field] is False
    _write_mode_0600(tmp_path / evidence.REPORT_PATH, report_raw + b" ")
    with pytest.raises(ValueError, match="external V1.1 audit"):
        evidence.verify_pinned_evidence(tmp_path)

    _write_mode_0600(tmp_path / evidence.REPORT_PATH, report_raw)
    _write_mode_0600(
        tmp_path / evidence.SCORE_TERM_SUPERSESSION_PATH,
        supersession_raw + b" ",
    )
    with pytest.raises(ValueError, match="supersession"):
        evidence.verify_pinned_evidence(tmp_path)


def test_pack_requires_supersession_before_collecting_or_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_collection(repo_root: Path) -> dict[str, bytes]:
        raise AssertionError("source collection must not start without supersession")

    monkeypatch.setattr(evidence, "_collect_source_members", fail_collection)
    with pytest.raises((FileNotFoundError, ValueError)):
        evidence.pack_evidence(tmp_path)
    assert not any(
        (tmp_path / path).exists()
        for path in (
            evidence.REPORT_PATH,
            evidence.ARCHIVE_PATH,
            evidence.MEMBERS_PATH,
            evidence.BUNDLE_PATH,
        )
    )


@pytest.mark.parametrize("directory_fsync_failure", (5, 6))
def test_pack_requires_reviewed_pins_and_rolls_back_partial_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_fsync_failure: int,
) -> None:
    source_members, report, _, archive_raw, members_raw, bundle_raw = _synthetic_bundle(
        monkeypatch
    )
    monkeypatch.setattr(
        evidence,
        "_collect_source_members",
        lambda repo_root: source_members,
    )
    monkeypatch.setattr(evidence, "_compress_zstd", lambda tar_raw: archive_raw)
    monkeypatch.setattr(evidence, "EXPECTED_EVIDENCE_ARCHIVE_SHA256", "0" * 64)
    _write_current_score_term_supersession(tmp_path, monkeypatch)
    output_paths = (
        evidence.REPORT_PATH,
        evidence.ARCHIVE_PATH,
        evidence.MEMBERS_PATH,
        evidence.BUNDLE_PATH,
    )

    with pytest.raises(ValueError, match="reviewed pins"):
        evidence.pack_evidence(tmp_path)
    assert not any((tmp_path / path).exists() for path in output_paths)

    pins = {
        "EXPECTED_EVIDENCE_ARCHIVE_SHA256": evidence._sha256_bytes(archive_raw),
        "EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256": evidence._sha256_bytes(members_raw),
        "EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256": evidence._sha256_bytes(bundle_raw),
        "EXPECTED_REPORT_SHA256": str(report["report_sha256"]),
    }
    for name, value in pins.items():
        monkeypatch.setattr(evidence, name, value)
    _write_current_score_term_supersession(tmp_path, monkeypatch)
    real_fsync = evidence.os.fsync
    directory_fsync_count = 0

    def fail_after_third_link(descriptor: int) -> None:
        nonlocal directory_fsync_count
        if evidence.stat.S_ISDIR(evidence.os.fstat(descriptor).st_mode):
            directory_fsync_count += 1
            if directory_fsync_count == directory_fsync_failure:
                raise OSError("fixture post-publication failure")
        real_fsync(descriptor)

    monkeypatch.setattr(evidence.os, "fsync", fail_after_third_link)
    with pytest.raises(OSError, match="fixture post-publication failure"):
        evidence.pack_evidence(tmp_path)
    assert not any((tmp_path / path).exists() for path in output_paths)
    assert directory_fsync_count >= 9


def test_pack_outer_rollback_continues_after_parent_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_members, report, _, archive_raw, members_raw, bundle_raw = _synthetic_bundle(
        monkeypatch
    )
    monkeypatch.setattr(
        evidence,
        "_collect_source_members",
        lambda repo_root: source_members,
    )
    monkeypatch.setattr(evidence, "_compress_zstd", lambda tar_raw: archive_raw)
    for name, value in {
        "EXPECTED_EVIDENCE_ARCHIVE_SHA256": evidence._sha256_bytes(archive_raw),
        "EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256": evidence._sha256_bytes(members_raw),
        "EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256": evidence._sha256_bytes(bundle_raw),
        "EXPECTED_REPORT_SHA256": str(report["report_sha256"]),
    }.items():
        monkeypatch.setattr(evidence, name, value)
    _write_current_score_term_supersession(tmp_path, monkeypatch)

    real_write = evidence._write_exclusive_owned
    write_count = 0

    def fail_third_write(
        repo_root: Path,
        relative_path: Path,
        payload: bytes,
    ) -> tuple[int, int]:
        nonlocal write_count
        write_count += 1
        if write_count == 3:
            raise OSError("fixture pre-link publication failure")
        return real_write(repo_root, relative_path, payload)

    real_open_parent = evidence.failure_atlas._owned_output_directory_descriptor
    parent_open_count = 0

    def fail_first_outer_open(repo_root: Path, relative: Path) -> int:
        nonlocal parent_open_count
        parent_open_count += 1
        if parent_open_count == 3:
            raise OSError("fixture outer rollback parent failure")
        return real_open_parent(repo_root, relative)

    monkeypatch.setattr(evidence, "_write_exclusive_owned", fail_third_write)
    monkeypatch.setattr(
        evidence.failure_atlas,
        "_owned_output_directory_descriptor",
        fail_first_outer_open,
    )
    with pytest.raises(RuntimeError, match="rollback was incomplete"):
        evidence.pack_evidence(tmp_path)

    assert not (tmp_path / evidence.REPORT_PATH).exists()
    assert (tmp_path / evidence.ARCHIVE_PATH).is_file()
    assert not (tmp_path / evidence.MEMBERS_PATH).exists()
    assert not (tmp_path / evidence.BUNDLE_PATH).exists()
