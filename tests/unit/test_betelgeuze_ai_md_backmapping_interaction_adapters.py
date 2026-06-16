from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from betelgeuze_ai_md.contracts import (
    BackmappedPose,
    InteractionEvidence,
    InteractionReport,
    build_backmapped_pose,
    build_interaction_report,
)
from betelgeuze_ai_md.contracts.backmapping_adapter import (
    BACKMAP_DEFAULT_POSE_ID,
    FAIL_CLOSED_BACKMAP_STATUSES,
    NON_PASSING_CHEMICAL_VALIDITY_STATUSES,
    PASSING_CHEMICAL_VALIDITY_STATUSES,
    SUPPORTED_BACKMAP_STATUSES,
)
from betelgeuze_ai_md.contracts.interaction_adapter import (
    INTERACTION_EVIDENCE_MISSING_BLOCKER,
    INTERACTION_ROLE_INVALID_BLOCKER,
    INTERACTION_UNSUPPORTED_TYPE_BLOCKER,
    ROLE_VALID_INTERACTION_TYPES,
    SUPPORTED_INTERACTION_TYPES,
)


def _module_text(module_name: str) -> str:
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and spec.origin is not None
    return Path(spec.origin).read_text(encoding="utf-8")


def test_backmapping_adapter_module_does_not_import_torch() -> None:
    text = _module_text("betelgeuze_ai_md.contracts.backmapping_adapter")
    assert "import torch" not in text
    assert "from torch" not in text


def test_interaction_adapter_module_does_not_import_torch() -> None:
    text = _module_text("betelgeuze_ai_md.contracts.interaction_adapter")
    assert "import torch" not in text
    assert "from torch" not in text


def test_onsps_ok_metadata_emits_passing_chemical_validity() -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": "pose_ok",
            "structure_path": "runs/pose_ok.sdf",
            "structure_sha256": "a" * 64,
            "repair_operations": ["kabsch_alignment", "element_check"],
            "backmap_status": "ok",
            "site_count": 4,
            "elements": ["O", "N", "S", "P"],
            "roles": ["acceptor", "donor", "donor", "acceptor"],
            "backmap_confidence": 0.92,
        }
    )

    assert isinstance(pose, BackmappedPose)
    assert pose.pose_id == "pose_ok"
    assert pose.structure_path == "runs/pose_ok.sdf"
    assert pose.structure_sha256 == "a" * 64
    assert pose.repair_operations == ["kabsch_alignment", "element_check"]
    assert pose.chemical_validity_summary["status"] == "pass"
    assert pose.chemical_validity_summary["check_id"] == "onsps_4bead_backmap"
    assert pose.chemical_validity_summary["site_count"] == 4
    assert pose.chemical_validity_summary["elements"] == ["O", "N", "S", "P"]
    assert pose.chemical_validity_summary["roles"] == ["acceptor", "donor", "donor", "acceptor"]
    assert not pose.chemical_validity_summary["claim_blockers"]
    assert 0.0 <= pose.backmap_confidence <= 1.0
    assert pose.backmap_confidence == 0.92


def test_onsps_ok_metadata_clamps_out_of_range_confidence() -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": "pose_clamp",
            "structure_path": "runs/pose_clamp.sdf",
            "structure_sha256": "b" * 64,
            "backmap_status": "ok",
            "site_count": 2,
            "elements": ["O", "N"],
            "roles": ["acceptor", "donor"],
            "backmap_confidence": 1.7,
        }
    )

    assert pose.backmap_confidence == 1.0
    assert pose.chemical_validity_summary["status"] == "pass"


def test_onsps_ok_with_no_sites_falls_back_to_fail_closed() -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": "pose_ok_empty_sites",
            "structure_path": "runs/pose_ok_empty.sdf",
            "structure_sha256": "c" * 64,
            "backmap_status": "ok",
            "site_count": 0,
        }
    )

    assert pose.chemical_validity_summary["status"] == "not_assessed"
    assert pose.backmap_confidence == 0.0
    assert "backmapping_chemical_validity_not_passed" in pose.chemical_validity_summary[
        "claim_blockers"
    ]


def test_no_onsps_sites_metadata_emits_fail_closed() -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": "pose_no_sites",
            "structure_path": "runs/pose_no_sites.sdf",
            "structure_sha256": "d" * 64,
            "backmap_status": "no_onsps_sites",
            "site_count": 0,
        }
    )

    assert pose.chemical_validity_summary["status"] == "not_assessed"
    assert "backmapping_no_onsps_sites" in pose.chemical_validity_summary["claim_blockers"]
    assert pose.backmap_confidence == 0.0


@pytest.mark.parametrize("status", sorted(FAIL_CLOSED_BACKMAP_STATUSES))
def test_fail_closed_backmap_statuses_emit_not_assessed_validity(status: str) -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": f"pose_{status}",
            "structure_path": f"runs/pose_{status}.sdf",
            "structure_sha256": "e" * 64,
            "backmap_status": status,
            "site_count": 0,
        }
    )

    assert pose.chemical_validity_summary["status"] in NON_PASSING_CHEMICAL_VALIDITY_STATUSES
    assert pose.backmap_confidence == 0.0
    assert pose.chemical_validity_summary["claim_blockers"]


def test_missing_metadata_falls_back_to_empty_input_blocker() -> None:
    pose = build_backmapped_pose()

    assert pose.pose_id == BACKMAP_DEFAULT_POSE_ID
    assert pose.chemical_validity_summary["status"] == "not_assessed"
    assert "backmapping_empty_input" in pose.chemical_validity_summary["claim_blockers"]
    assert pose.backmap_confidence == 0.0


def test_metadata_only_input_resolves_pose_fields() -> None:
    pose = build_backmapped_pose(
        metadata={
            "pose_id": "pose_meta",
            "structure_path": "runs/pose_meta.sdf",
            "structure_sha256": "f" * 64,
            "backmap_status": "ok",
            "site_count": 3,
            "elements": ["O", "N", "O"],
            "roles": ["acceptor", "donor", "acceptor"],
            "backmap_confidence": 0.81,
        }
    )

    assert pose.pose_id == "pose_meta"
    assert pose.chemical_validity_summary["status"] == "pass"
    assert pose.chemical_validity_summary["site_count"] == 3
    assert pose.backmap_confidence == 0.81


def test_invalid_existing_chemical_validity_is_overridden_when_ok() -> None:
    pose = build_backmapped_pose(
        {
            "pose_id": "pose_override",
            "structure_path": "runs/pose_override.sdf",
            "structure_sha256": "9" * 64,
            "backmap_status": "ok",
            "site_count": 2,
            "elements": ["O", "N"],
            "roles": ["acceptor", "donor"],
            "chemical_validity_summary": {"status": "fail", "claim_blockers": ["stale"]},
        }
    )

    assert pose.chemical_validity_summary["status"] == "pass"
    assert "stale" in pose.chemical_validity_summary["claim_blockers"]


def test_missing_interactions_emit_evidence_missing_blocker() -> None:
    report = build_interaction_report()

    assert isinstance(report, InteractionReport)
    assert report.interactions == []
    assert report.interaction_confidence == 0.0
    assert INTERACTION_EVIDENCE_MISSING_BLOCKER in report.claim_blockers


def test_missing_interactions_from_empty_mapping_emit_evidence_missing_blocker() -> None:
    report = build_interaction_report(
        {"interactions": [], "claim_blockers": []},
    )

    assert report.interactions == []
    assert INTERACTION_EVIDENCE_MISSING_BLOCKER in report.claim_blockers
    assert report.interaction_confidence == 0.0


def test_valid_interactions_emit_typed_evidence_rows() -> None:
    report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "hbond_001",
                "interaction_type": "hbond",
                "partners": ["SER:OG", "lig1:O1"],
                "distance": 2.9,
                "angle": 155.0,
                "occupancy": 0.6,
                "confidence": 0.78,
            },
            {
                "interaction_id": "sb_001",
                "interaction_type": "salt_bridge",
                "partners": ["LYS:NZ", "lig1:O3"],
                "distance": 3.4,
                "occupancy": 0.4,
                "confidence": 0.62,
            },
        ]
    )

    assert len(report.interactions) == 2
    assert all(isinstance(item, InteractionEvidence) for item in report.interactions)
    assert report.interactions[0].interaction_type == "hbond"
    assert report.interactions[0].partners == ["SER:OG", "lig1:O1"]
    assert report.interactions[0].distance == pytest.approx(2.9)
    assert report.interactions[0].angle == pytest.approx(155.0)
    assert report.interactions[0].role_valid is True
    assert not report.claim_blockers
    assert report.interaction_confidence == pytest.approx((0.78 + 0.62) / 2.0)


def test_role_invalid_interaction_adds_blocker_and_flags_row() -> None:
    report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "hbond_002",
                "interaction_type": "hbond",
                "partners": ["SER:OG", "lig1:O1"],
                "distance": 2.9,
                "occupancy": 0.5,
                "confidence": 0.7,
                "role_valid": False,
            }
        ]
    )

    assert INTERACTION_ROLE_INVALID_BLOCKER in report.claim_blockers
    assert report.interactions[0].role_valid is False
    assert report.interactions[0].interaction_type == "hbond"


def test_unsupported_interaction_type_adds_blocker_and_zeroes_confidence() -> None:
    report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "weird_001",
                "interaction_type": "weird_chemistry",
                "partners": ["A", "B"],
                "occupancy": 0.4,
                "confidence": 0.6,
            }
        ]
    )

    assert INTERACTION_UNSUPPORTED_TYPE_BLOCKER in report.claim_blockers
    assert report.interactions[0].interaction_type == "weird_chemistry"
    assert report.interactions[0].confidence == 0.0
    assert report.interaction_confidence == 0.0


def test_explicit_claim_blockers_in_source_are_preserved() -> None:
    report = build_interaction_report(
        {
            "interactions": [
                {
                    "interaction_id": "hbond_003",
                    "interaction_type": "hbond",
                    "partners": ["A", "B"],
                    "occupancy": 0.5,
                    "confidence": 0.5,
                }
            ],
            "claim_blockers": ["custom_blocker"],
        }
    )

    assert "custom_blocker" in report.claim_blockers
    assert not any(
        item in report.claim_blockers
        for item in (INTERACTION_ROLE_INVALID_BLOCKER, INTERACTION_UNSUPPORTED_TYPE_BLOCKER)
    )


def test_partner_fallback_resolves_minimum_two_partners() -> None:
    report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "single_partner",
                "interaction_type": "hbond",
                "partners": ["SER:OG"],
                "occupancy": 0.4,
                "confidence": 0.5,
            }
        ]
    )

    assert len(report.interactions[0].partners) >= 2
    assert report.interactions[0].partners[0] == "SER:OG"


def test_interaction_source_with_summary_metadata_overrides_confidence() -> None:
    report = build_interaction_report(
        {
            "interactions": [
                {
                    "interaction_id": "hbond_004",
                    "interaction_type": "hbond",
                    "partners": ["A", "B"],
                    "occupancy": 0.5,
                    "confidence": 0.5,
                }
            ],
            "interaction_confidence": 0.25,
            "over_anchoring_detected": True,
            "unsatisfied_donor_count": 1,
            "unsatisfied_acceptor_count": 2,
        }
    )

    assert report.interaction_confidence == pytest.approx(0.25)
    assert report.over_anchoring_detected is True
    assert report.unsatisfied_donor_count == 1
    assert report.unsatisfied_acceptor_count == 2


def test_supported_status_constants_are_stable() -> None:
    assert "ok" in SUPPORTED_BACKMAP_STATUSES
    assert "no_onsps_sites" in FAIL_CLOSED_BACKMAP_STATUSES
    assert "not_assessed" in NON_PASSING_CHEMICAL_VALIDITY_STATUSES
    assert "pass" in PASSING_CHEMICAL_VALIDITY_STATUSES
    assert {"hbond", "salt_bridge", "pi_stack"}.issubset(ROLE_VALID_INTERACTION_TYPES)
    assert "hbond" in SUPPORTED_INTERACTION_TYPES
    assert "salt_bridge" in SUPPORTED_INTERACTION_TYPES
