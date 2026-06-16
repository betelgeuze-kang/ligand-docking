from __future__ import annotations

import json

import pytest

from betelgeuze_ai_md.contracts import (
    AIResidualReport,
    AtomRecord,
    BackmappedPose,
    BondRecord,
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    CoarseState,
    EvidenceBundle,
    GENERAL_MD_ACCURACY_CLAIM,
    InteractionEvidence,
    InteractionReport,
    MolecularProject,
    MolecularSystem,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    TopologyValidityReport,
    TrajectorySummary,
    Verdict,
    fail_closed_topology_report,
)
from betelgeuze_ai_md.contracts.errors import ContractValidationError


def _safe_verdict() -> Verdict:
    return Verdict(
        claim_safe=True,
        verdict_label="delivery_ready",
        claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
        topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        confidence=0.82,
    )


def _bundle() -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="bundle_001",
        project_id="project_001",
        ranked_shortlist=[{"ligand_id": "lig1", "rank": 1, "score": -1.25}],
        trajectory_summary=TrajectorySummary(
            frame_count=3,
            energy_trace=[1.0, 0.2, -0.4],
            contact_trace=[0.1, 0.4, 0.8],
            stability_score=0.7,
            mean_min_distance=2.6,
        ),
        backmapped_poses=[
            BackmappedPose(
                pose_id="pose_001",
                structure_path="runs/example/pose_001.sdf",
                structure_sha256="a" * 64,
                chemical_validity_summary={"status": "pass"},
                backmap_confidence=0.91,
            )
        ],
        interaction_report=InteractionReport(
            interactions=[
                InteractionEvidence(
                    interaction_id="hbond_001",
                    interaction_type="hbond",
                    partners=["SER:OG", "lig1:O1"],
                    distance=2.8,
                    angle=158.0,
                    occupancy=0.66,
                    confidence=0.8,
                )
            ],
            interaction_confidence=0.77,
        ),
        topology_report=TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            validity_rows=[{"check_id": "sequence_mapped", "status": "pass"}],
        ),
        ai_residual_report=AIResidualReport(
            residual_mode="shadow",
            correction_applied=False,
            uncertainty=0.35,
            abstained=True,
            model_hash="m" * 64,
        ),
        failure_flags=[],
        source_hashes={
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        viewer_assets=["viewer/index.html"],
        wetlab_handoff_table=[{"ligand_id": "lig1", "recommendation": "review"}],
        verdict=_safe_verdict(),
    )


def test_contracts_serialize_and_hash_deterministically() -> None:
    project = MolecularProject(
        project_id="project_001",
        target_id="ADRB2",
        family="GPCR",
        receptor_structure="inputs/adrb2.pdb",
        ligand_library=[{"ligand_id": "lig1", "smiles": "CCO"}],
        pocket_definition={"center": [0.0, 0.0, 0.0], "radius": 12.0},
    )
    system = MolecularSystem(
        system_id="system_001",
        atoms=[
            AtomRecord("A1", "C", (0.0, 0.0, 0.0), molecule_id="protein"),
            AtomRecord("A2", "O", (1.2, 0.0, 0.0), molecule_id="ligand", charge=-0.2),
        ],
        bonds=[BondRecord("A1", "A2", 1)],
        topology_report={"status": "pass"},
    )
    state = CoarseState(
        x=[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
        v=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        mass=[12.0, 16.0],
        charge=[0.0, -0.2],
        bead_type=[1, 11],
        molecule_id=[0, 1],
        residue_id=[1, 1],
        mask=[True, True],
    )
    bundle = _bundle()

    payload = bundle.to_dict()
    assert payload["bundle_schema_version"] == "ai_md_evidence_bundle_v1"
    assert payload["trajectory_summary"]["frame_count"] == 3
    assert payload["topology_report"]["status"] == "pass"
    assert payload["topology_report"]["topology_fidelity"] == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    assert len(bundle.fingerprint()) == 64
    assert project.contract_hash() == project.contract_hash()
    assert system.contract_hash() == system.contract_hash()
    assert state.contract_hash() == state.contract_hash()
    assert json.loads(bundle.canonical_json())["bundle_id"] == "bundle_001"


def test_trajectory_summary_rejects_nonfinite_or_unbounded_metrics() -> None:
    with pytest.raises(ContractValidationError, match="energy_trace must be finite"):
        TrajectorySummary(frame_count=1, energy_trace=[float("nan")])

    with pytest.raises(ContractValidationError, match="contact_trace values must be non-negative"):
        TrajectorySummary(frame_count=1, contact_trace=[-1.0])

    with pytest.raises(ContractValidationError, match="stability_score must be in"):
        TrajectorySummary(frame_count=1, stability_score=1.2)

    with pytest.raises(ContractValidationError, match="mean_min_distance must be non-negative"):
        TrajectorySummary(frame_count=1, mean_min_distance=-0.1)

    with pytest.raises(ContractValidationError, match="escape_fraction must be in"):
        TrajectorySummary(frame_count=1, escape_fraction=1.1)

    with pytest.raises(ContractValidationError, match="trajectory traces cannot exceed frame_count"):
        TrajectorySummary(frame_count=1, energy_trace=[0.0, 0.1])


def test_claim_safe_bundle_requires_hashes_and_passing_topology() -> None:
    bundle = _bundle()
    source_hashes = dict(bundle.source_hashes)
    source_hashes.pop("model_hash")

    with pytest.raises(ContractValidationError, match="missing source hashes"):
        EvidenceBundle(**{**bundle.to_dict(), "source_hashes": source_hashes})

    with pytest.raises(ContractValidationError, match="passing topology"):
        EvidenceBundle(
            **{**bundle.to_dict(), "topology_report": {"status": "blocked", "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED}}
        )


def test_claim_safe_bundle_requires_product_output_tables() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValidationError, match="ranked shortlist"):
        EvidenceBundle(**{**bundle.to_dict(), "ranked_shortlist": []})

    with pytest.raises(ContractValidationError, match="wetlab handoff table"):
        EvidenceBundle(**{**bundle.to_dict(), "wetlab_handoff_table": []})


def test_claim_safe_bundle_requires_coarse_dynamics_summary() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValidationError, match="trajectory frames"):
        EvidenceBundle(**{**bundle.to_dict(), "trajectory_summary": {"frame_count": 0}})

    with pytest.raises(ContractValidationError, match="trajectory energy trace"):
        EvidenceBundle(
            **{
                **bundle.to_dict(),
                "trajectory_summary": {
                    "frame_count": 1,
                    "energy_trace": [],
                    "contact_trace": [0.0],
                    "stability_score": 0.5,
                    "mean_min_distance": 2.0,
                },
            }
        )


def test_claim_safe_bundle_requires_backmapped_pose_evidence() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValidationError, match="backmapped poses"):
        EvidenceBundle(**{**bundle.to_dict(), "backmapped_poses": []})


def test_claim_safe_bundle_requires_interaction_evidence() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValidationError, match="interaction evidence"):
        EvidenceBundle(
            **{
                **bundle.to_dict(),
                "interaction_report": {"interactions": [], "interaction_confidence": 0.7},
            }
        )

    with pytest.raises(ContractValidationError, match="positive interaction confidence"):
        EvidenceBundle(
            **{
                **bundle.to_dict(),
                "interaction_report": {
                    "interactions": [
                        {
                            "interaction_id": "hbond_001",
                            "interaction_type": "hbond",
                            "partners": ["SER:OG", "lig1:O1"],
                            "occupancy": 0.6,
                            "confidence": 0.8,
                        }
                    ],
                    "interaction_confidence": 0.0,
                },
            }
        )


def test_claim_safe_bundle_rejects_high_ai_uncertainty_or_review_flags() -> None:
    bundle = _bundle()

    with pytest.raises(ContractValidationError, match="high AI uncertainty"):
        EvidenceBundle(
            **{
                **bundle.to_dict(),
                "ai_residual_report": {
                    **bundle.ai_residual_report.to_dict(),
                    "uncertainty": 0.36,
                },
            }
        )

    with pytest.raises(ContractValidationError, match="AI residual review flags"):
        EvidenceBundle(
            **{
                **bundle.to_dict(),
                "ai_residual_report": {
                    **bundle.ai_residual_report.to_dict(),
                    "review_flags": ["residual_delta_review_required"],
                },
            }
        )


def test_evidence_bundle_accepts_topology_dict_or_instance() -> None:
    bundle = _bundle()
    as_dict = bundle.to_dict()
    rebuilt = EvidenceBundle(**as_dict)
    assert isinstance(rebuilt.topology_report, TopologyValidityReport)
    assert rebuilt.topology_report.status == "pass"
    assert rebuilt.topology_report.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    assert rebuilt.fingerprint() == bundle.fingerprint()


def test_claim_safe_bundle_rejects_placeholder_topology_fidelity() -> None:
    bundle = _bundle()
    payload = bundle.to_dict()
    payload["topology_report"] = {
        "status": "pass",
        "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    }

    with pytest.raises(ContractValidationError, match="non-placeholder topology fidelity"):
        EvidenceBundle(**payload)


def test_claim_safe_bundle_rejects_topology_claim_blockers() -> None:
    bundle = _bundle()
    payload = bundle.to_dict()
    payload["topology_report"] = {
        "status": "pass",
        "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        "claim_blockers": ["sequence_mapping_unresolved"],
    }

    with pytest.raises(ContractValidationError, match="topology claim blockers"):
        EvidenceBundle(**payload)


def test_claim_safe_bundle_rejects_chemical_validity_claim_blockers() -> None:
    bundle = _bundle()
    payload = bundle.to_dict()
    payload["backmapped_poses"][0]["chemical_validity_summary"] = {
        "status": "pass",
        "claim_blockers": ["stale_backmap_blocker"],
    }

    with pytest.raises(ContractValidationError, match="chemical validity claim blockers"):
        EvidenceBundle(**payload)


def test_claim_safe_bundle_rejects_verdict_topology_fidelity_mismatch() -> None:
    bundle = _bundle()
    payload = bundle.to_dict()
    payload["verdict"] = {
        **payload["verdict"],
        "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    }

    with pytest.raises(ContractValidationError, match="fidelity to match verdict fidelity"):
        EvidenceBundle(**payload)


def test_topology_validity_report_from_mapping_preserves_legacy_metadata() -> None:
    report = TopologyValidityReport.from_mapping(
        {
            "status": "pass",
            "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "confidence": 0.6,
            "atom_count": 128,
            "ligand_graph_valid": True,
            "metadata": {"source": "legacy_runner"},
        }
    )

    assert report.status == "pass"
    assert report.metadata == {
        "atom_count": 128,
        "ligand_graph_valid": True,
        "source": "legacy_runner",
    }


def test_topology_validity_report_rejects_invalid_confidence() -> None:
    with pytest.raises(ContractValidationError, match="confidence"):
        TopologyValidityReport(
            status="pass",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            confidence=1.5,
        )


def test_fail_closed_topology_report_uses_placeholder_and_claim_blocker() -> None:
    report = fail_closed_topology_report()
    assert report.status == "not_assessed"
    assert report.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert "topology_validity_not_assessed" in report.claim_blockers
    assert report.confidence == 0.0


def test_general_md_accuracy_claim_is_forbidden() -> None:
    with pytest.raises(ContractValidationError, match="general-MD-accuracy"):
        Verdict(
            claim_safe=False,
            verdict_label="blocked",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            accuracy_claim_grade=GENERAL_MD_ACCURACY_CLAIM,
        )


def test_ai_residual_report_records_bounded_score_delta_and_review_flag() -> None:
    report = AIResidualReport(
        residual_mode="assist",
        correction_applied=True,
        uncertainty=0.2,
        abstained=False,
        residual_delta=2.0,
        bounded_residual_delta=0.6,
        max_delta=1.0,
        guard=0.75,
        lambda_ai=1.0,
        active_score_col="binding_score_composite_v7_residual_active",
        base_score_col="binding_score_composite_v7",
        ranking_changed=True,
        guard_components={"topology": 1.0, "domain": 0.75, "calibration": 1.0},
    )

    payload = report.to_dict()
    assert payload["bounded_residual_delta"] == 0.6
    assert payload["active_score_col"] == "binding_score_composite_v7_residual_active"
    assert payload["ranking_changed"] is True
    assert "residual_delta_review_required" in payload["review_flags"]


def test_ai_residual_report_rejects_unbounded_or_unreported_ranking_change() -> None:
    with pytest.raises(ContractValidationError, match="guarded max_delta"):
        AIResidualReport(
            residual_mode="assist",
            correction_applied=True,
            bounded_residual_delta=1.1,
            max_delta=1.0,
            guard=1.0,
        )

    with pytest.raises(ContractValidationError, match="active_score_col"):
        AIResidualReport(ranking_changed=True, bounded_residual_delta=0.1, max_delta=1.0, guard=1.0)


def test_system_and_state_validation_fail_closed() -> None:
    with pytest.raises(ContractValidationError, match="unknown atom_id"):
        MolecularSystem(
            system_id="bad_system",
            atoms=[AtomRecord("A1", "C", (0, 0, 0))],
            bonds=[BondRecord("A1", "A2")],
        )

    with pytest.raises(ContractValidationError, match="mass values"):
        CoarseState(
            x=[[0, 0, 0]],
            v=[[0, 0, 0]],
            mass=[0.0],
            charge=[0.0],
            bead_type=[1],
            molecule_id=[0],
            residue_id=[0],
            mask=[True],
        )
