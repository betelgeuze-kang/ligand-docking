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


def test_compact_analysis_is_fully_recomputed_from_restored_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "5SD5_HWI"
    monkeypatch.setattr(evidence, "EXPECTED_CASE_IDS", (case_id,))
    path = "analysis.json"
    run_root = "run"
    source_path = f"{run_root}/receipts/engine_v2/{case_id}.json"
    result = _successful_frozen_result("baseline")
    source_receipts = {source_path: "a" * 64}
    payload = evidence.score_term_analysis.analyze_validated_results(
        [result],
        source_receipts_sha256=source_receipts,
        allowed_proposal_modes=tuple(sorted(evidence.EXPECTED_BASE_PROPOSAL_MODES)),
    )
    members = {path: evidence._canonical_bytes(payload) + b"\n"}

    observed = evidence._analysis(
        members,
        path,
        lane="fixture",
        run_root=run_root,
        receipt_hashes={case_id: "a" * 64},
        results={case_id: result},
    )
    assert observed["report_sha256"] == payload["report_sha256"]

    tampered = deepcopy(payload)
    tampered["term_summary"]["typed_vdw"]["removed_top1_changed_case_count"] += 1
    tampered["report_sha256"] = evidence._sha256_payload(
        {key: value for key, value in tampered.items() if key != "report_sha256"}
    )
    members[path] = evidence._canonical_bytes(tampered) + b"\n"
    with pytest.raises(ValueError, match="candidate terms"):
        evidence._analysis(
            members,
            path,
            lane="fixture",
            run_root=run_root,
            receipt_hashes={case_id: "a" * 64},
            results={case_id: result},
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
        "candidate_denominator_changed": False,
        "result_dependent_allocation": False,
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
    proposal_modes = [
        (
            evidence.PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            if index in rescue_parent_by_target
            else (
                "uniform_v3_rigid_ensemble"
                if index in v3_parent_by_target
                else "uniform_fallback"
            )
        )
        for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
    ]
    baseline_modes = [
        (
            "uniform_v3_rigid_ensemble"
            if index in baseline_parent_by_target
            else "uniform_fallback"
        )
        for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
    ]
    baseline_guided: dict[str, object] = {
        "schema_id": evidence.EXPECTED_BASELINE_GUIDED_PLACEMENT_SCHEMA_ID,
        "proposal_guidance_rows": [
            {
                "proposal_index": index,
                "mode": baseline_modes[index],
                "ensemble_source_proposal_index": baseline_parent_by_target.get(index),
            }
            for index in range(evidence.EXPECTED_CANDIDATE_COUNT)
        ],
        "proposal_modes": baseline_modes,
        "proposal_fingerprint_sha256s": [
            slot["proposal_fingerprint_sha256"] for slot in candidate_slots
        ],
    }
    baseline_guided["receipt_sha256"] = evidence._sha256_payload(baseline_guided)
    guided: dict[str, object] = {
        "schema_id": evidence.EXPECTED_RESCUE_GUIDED_PLACEMENT_SCHEMA_ID,
        "baseline_guided_receipt_sha256": baseline_guided["receipt_sha256"],
        "torsion_rescue_allocation_sha256": allocation["allocation_sha256"],
        "proposal_guidance_rows": [
            {
                "proposal_index": index,
                "mode": proposal_modes[index],
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
    }
    guided["receipt_sha256"] = evidence._sha256_payload(guided)
    proposal: dict[str, object] = {
        "schema_id": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_PROPOSAL_SCHEMA_ID
        ),
        "rescue_policy": _frozen_rescue_policy(),
        "rescue_policy_sha256": (
            evidence.EXPECTED_SOURCE_PAIRED_TORSION_RESCUE_POLICY_SHA256
        ),
        "candidate_count": evidence.EXPECTED_CANDIDATE_COUNT,
        "candidate_slots": candidate_slots,
        "baseline_guided_placement": baseline_guided,
        "guided_placement": guided,
        "result_dependent_allocation": False,
        "allocation": allocation,
    }
    proposal["receipt_sha256"] = evidence._sha256_payload(proposal)
    candidates: list[dict[str, object]] = []
    for index in range(evidence.EXPECTED_CANDIDATE_COUNT):
        rescue_parent = rescue_parent_by_target.get(index)
        v3_parent = v3_parent_by_target.get(index)
        candidate: dict[str, object] = {
            "proposal_index": index,
            "proposal_fingerprint_sha256": candidate_slots[index][
                "proposal_fingerprint_sha256"
            ],
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
            },
        }
        if rescue_parent is not None:
            candidate["refinement_receipt_payload"].update(
                {
                    "source_paired_parent_proposal_index": rescue_parent,
                    "source_paired_torsion_rescue_pairs": rescue_pairs,
                    "source_paired_torsion_rescue_allocation_sha256": allocation[
                        "allocation_sha256"
                    ],
                }
            )
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
        expected = "baseline guided lineage"

    with pytest.raises(ValueError, match=expected):
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
    return source_members, report, report_raw, archive_raw, members_raw, bundle_raw


def _write_mode_0600(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(0o600)


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


def test_frozen_result_parser_is_live_schema_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics = {
        field: None for field in evidence.EXPECTED_BASELINE_DIAGNOSTIC_FIELDS
    }
    diagnostics.update(
        {
            "schema_id": evidence.EXPECTED_BASELINE_DIAGNOSTIC_SCHEMA_ID,
            "preparation_status": "failure",
            "preparation_failure_code": "unsupported_large_ring_system",
            "candidate_budget": evidence.EXPECTED_CANDIDATE_COUNT,
            "candidate_success_count": 0,
            "candidate_failure_count": 0,
            "candidates": [],
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
    _pin_fixture_execution_contract(
        monkeypatch,
        lane="baseline",
        case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        result=result,
    )

    assert (
        evidence._historical_v11_result(
            result,
            lane="baseline",
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
            lane="baseline",
            case_id=evidence.EXPECTED_PREPARATION_FAILURE_CASE_ID,
        )

    drifted = {**result, "future_live_field": "must-not-be-accepted"}
    with pytest.raises(ValueError, match="result shape"):
        evidence._historical_v11_result(
            drifted,
            lane="baseline",
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
                    "torsion_selected": False,
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
            "scorer_backend_receipt": deepcopy(
                evidence.EXPECTED_SCORER_BACKEND_RECEIPT
            ),
        }
    )
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
        "score_terms",
        "score_scalar",
        "rescue_profile",
        "rescue_policy",
        "rescue_variant_cap",
        "result_dependent_eligibility",
        "refiner_config",
        "generic_refiner_config",
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
    if drift == "proposal_mode":
        candidate["proposal_mode"] = "future_unknown_mode"
    elif drift == "ensemble_lineage":
        candidate["ensemble_source_proposal_index"] = 1
    elif drift == "posebusters_flags":
        candidate["geometric_valid"] = False
    elif drift == "score_terms":
        candidate["score_term_binary64_hex"]["total_score"] = (999.0).hex()
    elif drift == "score_scalar":
        candidate["score"] = 0.5
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
        **expected,
    )

    assert observed == report
    assert identity["report_sha256"] == report_sha256
    with pytest.raises(ValueError, match="archive bundle identity"):
        evidence._verify_bundle_bytes(
            archive_raw=archive_raw,
            members_raw=members_raw,
            bundle_raw=bundle_raw,
            **{**expected, "expected_archive_sha256": "0" * 64},
        )


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
    for relative, raw in (
        (evidence.ARCHIVE_PATH, archive_raw),
        (evidence.MEMBERS_PATH, members_raw),
        (evidence.BUNDLE_PATH, bundle_raw),
        (evidence.REPORT_PATH, report_raw),
    ):
        _write_mode_0600(tmp_path / relative, raw)

    observed, _ = evidence.verify_pinned_evidence(tmp_path)

    assert observed == report
    _write_mode_0600(tmp_path / evidence.REPORT_PATH, report_raw + b" ")
    with pytest.raises(ValueError, match="external V1.1 audit"):
        evidence.verify_pinned_evidence(tmp_path)


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
