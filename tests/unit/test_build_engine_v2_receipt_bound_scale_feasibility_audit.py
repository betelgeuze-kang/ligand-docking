from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest

import tools.build_engine_v2_receipt_bound_scale_feasibility_audit as audit_builder
import tools.build_engine_v2_source_paired_failure_atlas as failure_atlas


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _authenticated_failure_atlas() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": failure_atlas.SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "development_only": True,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "stage0_eligible": False,
        "primary_claim_eligible": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "case_ids": list(audit_builder.EXPECTED_CASE_IDS),
        "ab_report_sha256": "a" * 64,
        "authentication": {
            "status": "verified_archive_member_bundle",
            "both_raw_receipt_lanes_verified": True,
        },
        "input_evidence": {
            "archive_sha256": audit_builder.failure_atlas.EXPECTED_EVIDENCE_ARCHIVE_SHA256,
            "member_manifest_sha256": (
                audit_builder.failure_atlas.EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256
            ),
            "bundle_checksum_sha256": (
                audit_builder.failure_atlas.EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256
            ),
        },
    }
    payload["report_sha256"] = _sha256(payload)
    return payload


def _rescue_payload(
    *,
    parent_index: int,
    evaluated: bool,
    available: bool,
) -> dict[str, object]:
    return {
        "schema_id": failure_atlas.SOURCE_PAIRED_RESCUE_RECEIPT_SCHEMA_ID,
        "source_paired_parent_proposal_index": parent_index,
        "torsion_evaluated": evaluated,
        "torsion_variant_available": available,
        "torsion_selected": False,
        "minimum_selected_final_receptor_penalty_binary64_hex": (2.0).hex(),
        "maximum_selected_final_receptor_penalty_binary64_hex": (4.0).hex(),
        "baseline_v6_receptor_penalty_binary64_hex": (6.0).hex(),
        "optimized_receptor_penalty_binary64_hex": (5.0).hex(),
        "baseline_v6_internal_penalty_binary64_hex": (2.0).hex(),
        "optimized_internal_penalty_binary64_hex": (1.0).hex(),
    }


def _results() -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for case_id in failure_atlas.EXPECTED_CASE_IDS:
        if case_id not in audit_builder.EXPECTED_HEAVY_ATOM_PROFILES:
            results[case_id] = {
                "case_id": case_id,
                "engine_id": "engine_v2",
                "status": "success",
                "native_artifact_sha256": "f" * 64,
                "engine_v2_diagnostics": {
                    "ligand_atom_count": 1,
                    "candidates": [],
                },
            }
            continue
        heavy_atom_count, native_sha256 = audit_builder.EXPECTED_HEAVY_ATOM_PROFILES[
            case_id
        ]
        candidates: list[dict[str, object]] = []
        for target_index, parent_index in ((8, 24), (13, 37), (18, 50), (23, 63)):
            if audit_builder.EXPECTED_ALLOCATION_COUNTS[case_id] == 0:
                break
            evaluated = not (case_id == "6VTA_AKN" and target_index == 23)
            available = evaluated and not (case_id == "5SD5_HWI" and target_index == 8)
            candidates.append(
                {
                    "proposal_index": target_index,
                    "proposal_mode": (
                        failure_atlas.PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
                    ),
                    "torsion_rescue_parent_proposal_index": parent_index,
                    "refinement_receipt_payload": _rescue_payload(
                        parent_index=parent_index,
                        evaluated=evaluated,
                        available=available,
                    ),
                }
            )
        results[case_id] = {
            "case_id": case_id,
            "engine_id": "engine_v2",
            "status": "success",
            "native_artifact_sha256": native_sha256,
            "engine_v2_diagnostics": {
                "ligand_atom_count": heavy_atom_count,
                "candidates": candidates,
            },
        }
    return results


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value))
    return set()


def _build_authenticated_report(
    monkeypatch: pytest.MonkeyPatch,
    *,
    authenticated_atlas: dict[str, object] | None = None,
    results: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    monkeypatch.setattr(
        audit_builder,
        "_load_authenticated_inputs",
        lambda **_kwargs: (
            authenticated_atlas or _authenticated_failure_atlas(),
            results or _results(),
        ),
    )
    return audit_builder.build_authenticated_scale_feasibility_audit(
        repo_root=Path("."),
        archive_path=Path(".betelgeuze/archive.tar.zst"),
        members_path=Path(".betelgeuze/archive.members.sha256"),
        bundle_path=Path(".betelgeuze/archive.bundle.sha256"),
        report_member=".betelgeuze/report.json",
        expected_archive_sha256="a" * 64,
        expected_members_sha256="b" * 64,
        expected_bundle_sha256="c" * 64,
        expected_report_sha256="d" * 64,
    )


def test_receipt_bound_audit_emits_exact_descriptive_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _build_authenticated_report(monkeypatch)

    assert report["schema_id"] == audit_builder.SCHEMA_ID
    assert report["historical_cohort_outcome_selected"] is True
    assert report["outcomes_consumed_for_cohort_authentication"] is True
    assert report["scale_computation_result_independent"] is True
    assert report["rmsd_used_in_scale_computation"] is False
    assert report["posebusters_used_in_scale_computation"] is False
    assert audit_builder.EXPECTED_HEAVY_ATOM_PROFILE_MANIFEST_SHA256 == (
        "57e9e27bd3d8a0752b81c0ce326c4f198bcf41b0529fb75dde3afe12fd67453b"
    )
    assert report["authentication"]["heavy_atom_profile_manifest_sha256"] == (
        audit_builder.EXPECTED_HEAVY_ATOM_PROFILE_MANIFEST_SHA256
    )
    assert report["case_ids"] == list(audit_builder.EXPECTED_CASE_IDS)
    assert report["summary"]["allocated_candidate_count"] == 24
    assert report["summary"]["evaluated_candidate_count"] == 23
    assert report["summary"]["variant_available_candidate_count"] == 22
    assert report["summary"]["selected_candidate_count"] == 0
    assert report["summary"]["current_absolute_window_counts"] == {
        "inside_2_inclusive_4_exclusive": 0,
        "outside_2_inclusive_4_exclusive": 22,
    }
    assert report["summary"]["diagnostic_heavy_atom_normalized_window_counts"] == {
        "interpretation": "current_numeric_bounds_reused_for_scale_comparison_only",
        "inside_2_inclusive_4_exclusive": 0,
        "outside_2_inclusive_4_exclusive": 22,
    }
    assert report["summary"]["exact_lexicographic_receptor_then_internal_counts"] == {
        "improved": 22,
        "equal": 0,
        "regressed": 0,
    }
    first_case = report["cases"][0]
    assert (
        first_case["heavy_atom_normalized_receptor_penalty"]["optimized"][
            "minimum_binary64_hex"
        ]
        == (5.0 / 29).hex()
    )
    assert report["decision"]["selected_rule"] is None
    assert report["decision"]["automatic_policy_change_allowed"] is False
    assert report["report_sha256"] == _sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    prohibited = {
        "rmsd_angstroms",
        "posebusters_failed_check_ids",
        "score_term_binary64_hex",
        "pre_coordinates_sha256",
        "post_coordinates_sha256",
        "coordinates",
    }
    assert not (_all_keys(report) & prohibited)


def test_heavy_atom_profile_requires_native_artifact_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = _results()
    results["5SD5_HWI"]["native_artifact_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="heavy-atom profile is not artifact-bound"):
        _build_authenticated_report(monkeypatch, results=results)


def test_missing_objective_is_unavailable_not_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = _results()
    candidate = results["5SIS_JSM"]["engine_v2_diagnostics"]["candidates"][0]
    candidate["refinement_receipt_payload"].pop(
        "optimized_internal_penalty_binary64_hex"
    )

    with pytest.raises(ValueError, match="canonical binary64 hex"):
        _build_authenticated_report(monkeypatch, results=results)


def test_pure_draft_cannot_emit_authoritative_audit() -> None:
    draft = audit_builder._build_scale_feasibility_audit_draft(
        rescue_results=_results()
    )

    assert "schema_id" not in draft
    assert "authentication" not in draft
    assert "report_sha256" not in draft


def test_authenticated_boundary_rejects_resealed_fresh_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticated_atlas = _authenticated_failure_atlas()
    authenticated_atlas["fresh_execution_authorized"] = True
    authenticated_atlas.pop("report_sha256")
    authenticated_atlas["report_sha256"] = _sha256(authenticated_atlas)

    with pytest.raises(ValueError, match="failure-atlas boundary"):
        _build_authenticated_report(
            monkeypatch,
            authenticated_atlas=authenticated_atlas,
        )


@pytest.mark.parametrize(
    ("baseline", "optimized", "expected"),
    (
        ((5.0, 2.0), (4.0, 9.0), "improved"),
        ((5.0, 2.0), (5.0, 1.0), "improved"),
        ((5.0, 2.0), (5.0, 2.0), "equal"),
        ((5.0, 2.0), (5.0, 3.0), "regressed"),
        ((5.0, 2.0), (6.0, 0.0), "regressed"),
    ),
)
def test_exact_lexicographic_order(
    baseline: tuple[float, float],
    optimized: tuple[float, float],
    expected: str,
) -> None:
    assert (
        audit_builder._exact_lexicographic_order(
            baseline_receptor=baseline[0],
            baseline_internal=baseline[1],
            optimized_receptor=optimized[0],
            optimized_internal=optimized[1],
        )
        == expected
    )


def test_main_writes_exclusive_mode_0600_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _build_authenticated_report(monkeypatch)
    monkeypatch.setattr(
        audit_builder,
        "build_authenticated_scale_feasibility_audit",
        lambda **_kwargs: report,
    )
    arguments = [
        "--repo-root",
        str(tmp_path),
        "--archive",
        ".betelgeuze/archive.tar.zst",
        "--members-sha256",
        ".betelgeuze/archive.members.sha256",
        "--bundle-sha256",
        ".betelgeuze/archive.bundle.sha256",
        "--report-member",
        ".betelgeuze/report.json",
        "--expected-archive-sha256",
        "a" * 64,
        "--expected-members-sha256",
        "b" * 64,
        "--expected-bundle-sha256",
        "c" * 64,
        "--expected-report-sha256",
        "d" * 64,
        "--output",
        ".betelgeuze/audit.json",
    ]

    assert audit_builder.main(arguments) == 0
    output = tmp_path / ".betelgeuze/audit.json"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(output.read_bytes()) == report
    with pytest.raises(FileExistsError):
        audit_builder.main(arguments)
