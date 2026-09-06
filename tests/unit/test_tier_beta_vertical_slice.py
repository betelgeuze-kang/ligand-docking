from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

import pytest
import torch

from api.result_manifest import verify_result_manifest
from betelgeuze_engine.biodiscovery.screening import (
    _LOCAL_MANIFEST_KEY,
    _parse_pdb_text,
)
from betelgeuze_engine.biodiscovery import TierBetaScreening
from betelgeuze_engine.physics.dense_guard import ensure_small_dense_diagnostic
from betelgeuze_engine.physics.forcefield import ProductForceField, guarded_force_term_registry
from betelgeuze_engine.physics.neighbor import full_neighbor_pairs
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_product.tier_beta_vertical_slice import TIER_BETA_DIRECT_RUNNER_PROFILE_ID
from tests.unit.test_biodiscovery_screening import MINI_PDB, VALID_SMILES

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_tier_beta_paths_do_not_use_subprocess_or_csv_handoff() -> None:
    paths = [
        "betelgeuze_engine/biodiscovery/contracts.py",
        "betelgeuze_engine/biodiscovery/ligand_prep.py",
        "betelgeuze_engine/biodiscovery/manifest.py",
        "betelgeuze_engine/biodiscovery/pose.py",
        "betelgeuze_engine/biodiscovery/protein_prep.py",
        "betelgeuze_engine/biodiscovery/scoring.py",
        "betelgeuze_engine/biodiscovery/screening.py",
        "betelgeuze_product/tier_beta_vertical_slice.py",
        "api/product_tier_beta.py",
        "betelgeuze_engine/product/runners/tier_beta_service_adapter.py",
        "tools/run_tier_beta_vertical_slice.py",
    ]
    forbidden_terms = [
        "subprocess",
        "pandas",
        "pd.",
        "read_csv",
        "to_csv",
        "csv.",
        "import csv",
        "NamedTemporaryFile",
        "TemporaryDirectory",
        "tempfile",
    ]

    violations: list[str] = []
    for relative_path in paths:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in text:
                violations.append(f"{relative_path}: {term}")

    assert violations == []


def _verify_local_manifest_signature(manifest: dict) -> bool:
    observed = str(manifest.get("signature") or "")
    payload = {key: value for key, value in manifest.items() if key != "signature"}
    expected = hmac.new(
        _LOCAL_MANIFEST_KEY.encode("utf-8"),
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(observed, expected)


def test_service_pdb_smiles_success_signed_manifest_and_claim_limits() -> None:
    result = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0).screen(
        protein_input=MINI_PDB,
        ligand_input=VALID_SMILES,
    )

    assert result.ok is True
    assert result.result_manifest["signature"]
    assert _verify_local_manifest_signature(result.result_manifest)
    assert result.manifest_hash == result.result_manifest["content_hash"]
    benchmark_summary = result.result_manifest["benchmark_metric_summary"]
    assert benchmark_summary["schema_version"] == "tier_beta_docking_gold_metrics_v1"
    assert benchmark_summary["status"] == "blocked_reference_pose_missing"
    assert benchmark_summary["reference_pose_present"] is False
    assert benchmark_summary["native_pose_present"] is False
    assert benchmark_summary["scored_pose_count"] >= result.poses_scored
    assert benchmark_summary["top1_mean_rmsd_a"] is None
    assert benchmark_summary["top5_best_mean_rmsd_a"] is None
    assert "native_or_reference_pose_missing" in benchmark_summary["blockers"]
    assert result.diagnostics["benchmark_metric_summary"] == benchmark_summary
    assert result.claim_metadata["benchmark_metric_summary"] == benchmark_summary
    assert result.claim_metadata["claim_safe"] is False
    assert "restricted_tier_beta_unvalidated" in result.claim_metadata["blocked_reason"]
    assert "calibrated_affinity" in result.claim_metadata["blocked_claims"]
    assert result.pose_scores[0]["pose_rank"] == 1
    assert "score_components" in result.pose_scores[0]
    assert result.pose_scores[0]["abstention"] is True
    assert result.pose_scores[0]["topology_fidelity"] == "sequence_mapped"
    assert result.pose_scores[0]["neighbor_diagnostics"]["nxn_allocation_observed"] is False
    assert result.pose_scores[0]["ligand_topology"]["bond_count"] > 0
    assert "pose_rmsd_to_top1_a" in result.pose_scores[0]
    assert "pose_rmsd_to_top5_centroid_a" in result.pose_scores[0]
    assert result.pose_scores[0]["clash_count"] >= 0
    assert result.pose_scores[0]["chemistry_validity"]["status"] == "chemical_validity_pass"
    assert result.pose_scores[0]["ranking_metric"]["name"] == "restricted_local_composite_score_v1"
    ligand_state = result.pose_scores[0]["ligand_state"]
    assert ligand_state["state_id"].startswith("ligand_state_")
    assert ligand_state["scoring_status"] == "pose_conformers_generated"
    assert ligand_state["protonation_source"] == "rdkit_formal_charge_input_plus_restricted_ph_range_heuristic"
    assert ligand_state["protonation_ph_values"] == (5.0, 7.4, 9.0)
    pose_search = result.pose_scores[0]["pose_search"]
    assert pose_search["schema_version"] == "tier_beta_pose_search_v1"
    assert pose_search["search_strategy"] == "etkdg_conformer_so3_translation_grid_coarse_score_local_min_beam_v1"
    assert pose_search["conformer_diversity"]["schema_version"] == "tier_beta_conformer_diversity_v1"
    assert pose_search["conformer_diversity"]["conformer_count"] >= 1
    assert pose_search["conformer_count"] == pose_search["conformer_diversity"]["conformer_count"]
    assert pose_search["rotatable_bond_count"] == pose_search["conformer_diversity"]["rotatable_bond_count"]
    assert pose_search["retained_conformer_count"] >= 1
    assert len(pose_search["retained_conformer_indices"]) == pose_search["retained_conformer_count"]
    assert 0.0 < pose_search["retained_conformer_fraction"] <= 1.0
    assert pose_search["rotations_per_conformer"] >= 4
    assert pose_search["translation_grid_point_count"] >= 7
    assert pose_search["raw_candidate_count"] > result.poses_scored
    assert pose_search["coarse_beam_candidate_count"] >= result.poses_scored
    assert pose_search["retained_candidate_count"] == result.poses_scored
    assert pose_search["coarse_score_beam_status"] == "pass"
    assert pose_search["coarse_score"] <= pose_search["coarse_score_before_local"] + 1e-8
    assert len(pose_search["translation_vector_a"]) == 3
    assert pose_search["local_minimization_status"].startswith("finite_difference_rigid_body_gradient_")
    assert pose_search["local_minimization_method"] == "finite_difference_gradient_descent_translation_rotation"
    assert pose_search["local_minimization_degrees_of_freedom"] == ["translation", "rotation"]
    assert pose_search["local_minimization"]["gradient_parameter_count"] == 6
    assert len(pose_search["local_minimization"]["rotation_delta_rad"]) == 3
    assert pose_search["local_minimization"]["final_coarse_score"] == pose_search["coarse_score"]
    assert pose_search["symmetry_rmsd_clustering_status"] == "symmetry_aware_rmsd_clustered"
    assert pose_search["symmetry_mapping_count"] >= 1
    assert pose_search["symmetry_cluster_count"] >= 1
    assert result.pose_scores[0]["pose_rmsd_method"] in {
        "rdkit_automorphism_min_rmsd",
        "identity_atom_order_rmsd",
    }
    assert result.pose_scores[0]["symmetry_aware_pose_rmsd_to_top1_a"] == 0.0
    assert result.pose_scores[0]["pose_rmsd_clustering"]["schema_version"] == "tier_beta_pose_rmsd_clustering_v1"
    anchor_mapping = pose_search["chemical_anchor_mapping"]
    assert anchor_mapping["schema_version"] == "tier_beta_ligand_anchor_mapping_v1"
    assert anchor_mapping["status"] == "rdkit_feature_charge_ring_graph_anchor_mapping"
    assert len(anchor_mapping["two_bead_anchor_atom_indices"]) == 2
    assert len(anchor_mapping["four_bead_anchor_atom_indices"]) == 4
    assert anchor_mapping["graph_distance_source"] == "rdkit_topological_distance_matrix"
    scoring_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "scoring_ranking")
    assert scoring_stage["diagnostics"]["pose_search"]["raw_candidate_count"] == pose_search["raw_candidate_count"]
    assert scoring_stage["diagnostics"]["pose_search"]["chemical_anchor_mapping"]["two_bead_anchor_atom_indices"]
    pose_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "pose_ensemble")
    state_ensemble = pose_stage["diagnostics"]["ligand_state_ensemble"]
    assert state_ensemble["status"] == "restricted_rdkit_standardized_state_ensemble_ph_range_no_pka_calibration"
    assert state_ensemble["scored_state_count"] >= 1
    refine_stage = next(stage for stage in result.stage_records if stage["stage_id"] == "top_k_refine")
    assert refine_stage["diagnostics"]["rmsd_clustering"]["status"] == "symmetry_aware_rmsd_clustered"
    assert result.result_manifest["stability"]["diagnostics"]["pbc_enabled"] is False
    assert result.result_manifest["stability"]["diagnostics"]["restart_reproducible"] is None
    assert result.failure_code == "none"
    assert result.typed_input["schema_version"] == result.schema_version
    assert result.typed_output["ok"] is True
    stage_ids = [stage["stage_id"] for stage in result.stage_records]
    assert stage_ids == [
        "protein_preparation",
        "topology_validation.protein",
        "topology_validation.ligand",
        "pose_ensemble",
        "pocket_resolution",
        "scoring_ranking",
        "top_k_refine",
        "stability_simulation",
    ]
    assert result.result_manifest["stage_records"][0]["schema_version"] == result.schema_version


def test_service_mmcif_smiles_success_signed_manifest() -> None:
    cif_path = FIXTURE_DIR / "mini_protein.cif"

    result = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0).screen(
        protein_input=str(cif_path),
        ligand_input=VALID_SMILES,
    )

    assert result.ok is True
    assert result.protein_sequence == "AGSLVFQWHT"
    assert result.protein_residue_count == 10
    assert result.pose_scores[0]["topology_fidelity"] == "sequence_mapped"
    assert result.pose_scores[0]["neighbor_diagnostics"]["nxn_allocation_observed"] is False
    assert result.result_manifest["signature"]
    assert _verify_local_manifest_signature(result.result_manifest)
    assert result.result_manifest["protein"]["residue_count"] == 10
    assert result.failure_code == "none"


def test_deterministic_replay_hash_and_pose_ranking_are_stable() -> None:
    kwargs = {
        "protein_input": MINI_PDB,
        "ligand_input": VALID_SMILES,
    }
    first = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0, seed=123).screen(**kwargs)
    second = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0, seed=123).screen(**kwargs)

    assert first.ok is True
    assert second.ok is True
    assert first.result_manifest["replay_hash"] == second.result_manifest["replay_hash"]
    assert first.pose_scores == second.pose_scores
    assert first.best_score == second.best_score
    assert first.result_manifest["ranking"] == second.result_manifest["ranking"]
    assert first.result_manifest["precision"] == second.result_manifest["precision"]
    assert first.result_manifest["stage_records"] == second.result_manifest["stage_records"]

    different_seed = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0, seed=124).screen(**kwargs)
    assert different_seed.ok is True
    assert different_seed.result_manifest["replay_hash"] != first.result_manifest["replay_hash"]


def test_service_pdb_sdf_success_preserves_molblock_topology_provenance() -> None:
    sdf_path = FIXTURE_DIR / "ethanol.sdf"

    result = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=0).screen(
        protein_input=MINI_PDB,
        ligand_input=str(sdf_path),
    )

    assert result.ok is True
    assert result.ligand_smiles == "CCO"
    row_topology = result.pose_scores[0]["ligand_topology"]
    assert row_topology["input_source_kind"] == "sdf_path"
    assert row_topology["input_provenance"]["format"] == "sdf_molblock"
    assert row_topology["atom_elements"] == ["C", "C", "O"]
    assert row_topology["formal_charges"] == [0, 0, 0]
    assert row_topology["bond_count"] == 2
    assert row_topology["feature_source"] == "rdkit_chemical_features_base_fdef"
    assert row_topology["donor_site_count"] == 1
    assert row_topology["acceptor_site_count"] == 1
    assert row_topology["hbond_site_count"] == 2
    assert {site["role"] for site in row_topology["feature_sites"] if site["atom_idx"] == 2} == {
        "donor",
        "acceptor",
    }
    assert row_topology["bonds"] == [
        {"begin_atom_idx": 0, "end_atom_idx": 1, "bond_type": "SINGLE", "is_aromatic": False},
        {"begin_atom_idx": 1, "end_atom_idx": 2, "bond_type": "SINGLE", "is_aromatic": False},
    ]
    assert row_topology["protonation_source"] == "sdf_path_molblock_atoms_no_enumeration"
    assert row_topology["tautomer_source"] == "sdf_path_molblock_connectivity_no_enumeration"
    assert result.claim_metadata["ligand_topology"] == row_topology
    assert result.result_manifest["claim_metadata"]["ligand_topology"] == row_topology
    assert _verify_local_manifest_signature(result.result_manifest)


@pytest.mark.parametrize(
    ("protein_input", "ligand_input", "expected"),
    [
        (MINI_PDB, "XxYyZz", "ligand_invalid"),
        (MINI_PDB, "CC(O)C(=O)O", "unassigned_ligand_chirality"),
        ("ATOM      1  CA  UNK A   1       1.0     0.0     0.0  1.00  0.00           C\n" * 10, VALID_SMILES, "placeholder_topology"),
        (
            MINI_PDB + "HETATM   99 ZN    ZN A  99       0.000   0.000   0.000  1.00  0.00          ZN\n",
            VALID_SMILES,
            "unsupported_metal",
        ),
        (
            MINI_PDB + "HETATM   99  C1  ATP A  99       0.000   0.000   0.000  1.00  0.00           C\n",
            VALID_SMILES,
            "unsupported_cofactor_or_bound_ligand",
        ),
    ],
)
def test_service_negative_paths_fail_closed(protein_input: str, ligand_input: str, expected: str) -> None:
    result = TierBetaScreening(device="cpu", pose_count=2, stability_steps=0).screen(
        protein_input=protein_input,
        ligand_input=ligand_input,
    )

    assert result.ok is False
    assert expected in result.blocked_reason
    assert result.manifest_hash == ""
    assert result.failure_code != "none"
    assert result.stage_records[-1]["status"] == "blocked"
    assert result.typed_output["failure_code"] == result.failure_code


def test_invalid_sdf_ligand_fails_closed_without_smiles_fallback() -> None:
    bad_sdf = """
  RDKit          2D

  0  0  0  0  0  0            999 V2000
M  END
$$$$
"""

    result = TierBetaScreening(device="cpu", pose_count=2, stability_steps=0).screen(
        protein_input=MINI_PDB,
        ligand_input=bad_sdf,
    )

    assert result.ok is False
    assert "invalid_sdf_ligand" in result.blocked_reason
    assert result.failure_code == "ligand_parse_failed"
    assert result.manifest_hash == ""


def test_placeholder_protein_parse_raises_for_metal() -> None:
    with pytest.raises(ValueError, match="unsupported_metal"):
        _parse_pdb_text(
            "HETATM    1 FE    FE A   1       0.000   0.000   0.000  1.00  0.00          FE\n"
        )


def test_mmcif_unsupported_cofactor_fails_closed() -> None:
    cofactor_cif = """
data_tier_beta_cofactor
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.pdbx_PDB_model_num
ATOM 1 C CA ALA A 1 0.000 0.000 0.000 1
HETATM 2 C C1 ATP A 2 1.000 0.000 0.000 1
#
"""

    result = TierBetaScreening(device="cpu", pose_count=2, stability_steps=0).screen(
        protein_input=cofactor_cif,
        ligand_input=VALID_SMILES,
    )

    assert result.ok is False
    assert result.failure_code == "unsupported_cofactor_or_bound_ligand"
    assert "unsupported_cofactor_or_bound_ligand" in result.blocked_reason
    assert result.manifest_hash == ""


def test_dense_and_reference_neighbor_bypass_regression() -> None:
    coords = torch.zeros((1, 513, 3), dtype=torch.float32)
    with pytest.raises(ValueError, match="dense NxN diagnostic"):
        ensure_small_dense_diagnostic(coords, context="unit_test")

    small = torch.randn((1, 12, 3), dtype=torch.float32)
    atom_types = torch.ones((12,), dtype=torch.long)
    pairs = full_neighbor_pairs(small, cutoff=8.0)
    field = ProductForceField.from_registry(guarded_force_term_registry())
    with pytest.raises(ValueError, match="NxN allocation|reference full pairs"):
        field.energy_forces(
            EngineState(coords=small, atom_types=atom_types),
            pairs,
            product_neighbor_required=True,
        )


def test_service_neighbor_overflow_fails_closed_before_signed_result(monkeypatch) -> None:
    import betelgeuze_engine.biodiscovery.screening as screening

    def _overflow_score(*_args, **_kwargs) -> tuple[float, dict]:
        return float("inf"), {
            "status": "blocked_neighbor_overflow",
            "neighbor_diagnostics": {
                "overflow": True,
                "nxn_allocation_observed": False,
            },
        }

    monkeypatch.setattr(screening, "_single_pose_score", _overflow_score)

    result = TierBetaScreening(device="cpu", pose_count=2, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB,
        ligand_input=VALID_SMILES,
    )

    assert result.ok is False
    assert result.failure_code == "neighbor_overflow"
    assert "neighbor_overflow" in result.blocked_reason
    assert result.manifest_hash == ""
    assert result.result_manifest == {}
    assert result.stage_records[-1]["status"] == "blocked"


def test_service_unsigned_result_manifest_fails_closed(monkeypatch) -> None:
    original_build_manifest = TierBetaScreening._build_manifest

    def _unsigned_manifest(self, *args, **kwargs) -> dict:
        manifest = dict(original_build_manifest(self, *args, **kwargs))
        manifest.pop("signature", None)
        return manifest

    monkeypatch.setattr(TierBetaScreening, "_build_manifest", _unsigned_manifest)

    result = TierBetaScreening(device="cpu", pose_count=2, top_k=1, stability_steps=0).screen(
        protein_input=MINI_PDB,
        ligand_input=VALID_SMILES,
    )

    assert result.ok is False
    assert result.failure_code == "unsigned_result_manifest"
    assert "unsigned_result_manifest" in result.blocked_reason
    assert result.manifest_hash == ""
    assert result.result_manifest == {}
    assert result.stage_records[-1]["status"] == "blocked"


def test_api_submit_worker_result_direct_e2e(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import api.main as api_main
    from api.config import settings

    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(settings, "api_inline_worker_enabled", True)
    api_main.job_store = None
    api_main._job_store_path = None

    client = TestClient(api_main.app)
    response = client.post(
        "/simulate",
        json={
            "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
            "target_name": "tier_beta_fixture",
            "runner_profile_params": {
                "protein_input": MINI_PDB,
                "ligand_input": VALID_SMILES,
                "pose_count": 4,
                "top_k": 2,
                "stability_steps": 0,
            },
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/status/{job_id}").json()
    assert status["status"] == "completed"
    result = client.get(f"/results/{job_id}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["result"]["ok"] is True
    assert payload["result_manifest"]["signature"]
    manifest_path = Path(status["result_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert verify_result_manifest(
        manifest,
        signing_key=settings.api_result_manifest_signing_key,
    )


def test_api_placeholder_topology_fails_closed_without_retry_or_result(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import api.main as api_main
    from api.config import settings

    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(settings, "api_inline_worker_enabled", True)
    api_main.job_store = None
    api_main._job_store_path = None
    placeholder = "ATOM      1  CA  UNK A   1       1.0     0.0     0.0  1.00  0.00           C\n" * 10

    client = TestClient(api_main.app)
    response = client.post(
        "/simulate",
        json={
            "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
            "target_name": "tier_beta_placeholder_negative",
            "runner_profile_params": {
                "protein_input": placeholder,
                "ligand_input": VALID_SMILES,
                "pose_count": 2,
                "top_k": 1,
                "stability_steps": 0,
            },
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/status/{job_id}").json()
    assert status["status"] == "failed"
    assert status["message"] == "protein_invalid: placeholder_topology"
    assert status["evidence_bundle"] is None
    manifest_path = Path(status["result_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["error"] == "protein_invalid: placeholder_topology"
    assert verify_result_manifest(
        manifest,
        signing_key=settings.api_result_manifest_signing_key,
    )
    assert client.get(f"/results/{job_id}").status_code == 400


def test_product_tier_beta_router_submit_worker_result_direct_e2e(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import api.main as api_main
    from api.config import settings

    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(settings, "api_inline_worker_enabled", True)
    api_main.job_store = None
    api_main._job_store_path = None

    client = TestClient(api_main.app)
    response = client.post(
        "/product/tier-beta/docking/jobs",
        json={
            "protein_input": MINI_PDB,
            "ligand_input": str(FIXTURE_DIR / "ethanol.sdf"),
            "pose_count": 4,
            "top_k": 2,
            "stability_steps": 0,
            "seed": 11,
        },
    )

    assert response.status_code == 200
    submit_payload = response.json()
    assert submit_payload["workflow_id"] == "tier_beta_biodiscovery_screening_v1"
    assert submit_payload["external_state_mutated"] is False
    job_id = submit_payload["job_id"]

    status = client.get(f"/status/{job_id}").json()
    assert status["status"] == "completed"
    manifest_path = Path(status["result_manifest"])
    evidence_path = Path(status["evidence_bundle"])
    assert manifest_path.exists()
    assert evidence_path.exists()
    assert len(status["evidence_bundle_sha256"]) == 64
    from betelgeuze_ai_md.contracts import EvidenceBundle

    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert EvidenceBundle(**evidence_payload).fingerprint() == status["evidence_bundle_sha256"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert verify_result_manifest(
        manifest,
        signing_key=settings.api_result_manifest_signing_key,
    )
    result_path = Path(manifest["result_file"])
    assert hashlib.sha256(result_path.read_bytes()).hexdigest() == manifest["result_file_sha256"]

    result = client.get(f"/results/{job_id}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["result"]["ok"] is True
    assert payload["result"]["ligand_smiles"] == "CCO"
    assert payload["docking_results_emitted"] is True
    topology = payload["result"]["pose_scores"][0]["ligand_topology"]
    assert topology["input_source_kind"] == "sdf_path"
    assert topology["atom_elements"] == ["C", "C", "O"]
    assert topology["bond_count"] == 2
    assert payload["result_manifest"]["signature"]
    assert payload["result"]["pose_scores"][0]["neighbor_diagnostics"]["nxn_allocation_observed"] is False


def test_product_tier_beta_router_placeholder_topology_fails_closed(tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import api.main as api_main
    from api.config import settings

    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(settings, "api_inline_worker_enabled", True)
    api_main.job_store = None
    api_main._job_store_path = None
    placeholder = "ATOM      1  CA  UNK A   1       1.0     0.0     0.0  1.00  0.00           C\n" * 10

    client = TestClient(api_main.app)
    response = client.post(
        "/product/tier-beta/docking/jobs",
        json={
            "protein_input": placeholder,
            "ligand_input": VALID_SMILES,
            "pose_count": 2,
            "top_k": 1,
            "stability_steps": 0,
        },
    )

    assert response.status_code == 200
    submit_payload = response.json()
    assert submit_payload["external_state_mutated"] is False
    assert submit_payload["workflow_id"] == "tier_beta_biodiscovery_screening_v1"
    job_id = submit_payload["job_id"]

    status = client.get(f"/status/{job_id}").json()
    assert status["status"] == "failed"
    assert status["message"] == "protein_invalid: placeholder_topology"
    assert status["evidence_bundle"] is None
    manifest_path = Path(status["result_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["error"] == "protein_invalid: placeholder_topology"
    assert verify_result_manifest(
        manifest,
        signing_key=settings.api_result_manifest_signing_key,
    )
    assert client.get(f"/results/{job_id}").status_code == 400


def test_cli_compatibility_wrapper(tmp_path) -> None:
    pdb_path = tmp_path / "fixture.pdb"
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    evidence_bundle_path = tmp_path / "evidence_bundle.json"
    pdb_path.write_text(MINI_PDB, encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_tier_beta_vertical_slice.py",
            "--protein-input",
            str(pdb_path),
            "--ligand-input",
            VALID_SMILES,
            "--result-json",
            str(result_path),
            "--manifest-json",
            str(manifest_path),
            "--evidence-bundle-json",
            str(evidence_bundle_path),
            "--pose-count",
            "4",
            "--top-k",
            "2",
            "--stability-steps",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["ok"] is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert verify_result_manifest(
        manifest,
        signing_key="local-dev-result-manifest-signing-key-change-me",
    )
    from betelgeuze_ai_md.contracts import EvidenceBundle

    evidence_payload = json.loads(evidence_bundle_path.read_text(encoding="utf-8"))
    bundle = EvidenceBundle(**evidence_payload)
    assert len(bundle.fingerprint()) == 64
    assert bundle.result_manifest["signature"] == manifest["signature"]
    assert bundle.verdict.claim_safe is False
    assert "delivery_bundle_validation_not_attached" in bundle.failure_flags


def test_cli_compatibility_wrapper_accepts_profile_request_json(tmp_path) -> None:
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    manifest_path = tmp_path / "manifest.json"
    evidence_bundle_path = tmp_path / "evidence_bundle.json"
    request_path.write_text(
        json.dumps(
            {
                "runner_profile_id": TIER_BETA_DIRECT_RUNNER_PROFILE_ID,
                "runner_profile_params": {
                    "protein_input": MINI_PDB,
                    "ligand_input": VALID_SMILES,
                    "pose_count": 4,
                    "top_k": 2,
                    "stability_steps": 0,
                    "seed": 42,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_tier_beta_vertical_slice.py",
            "--protein-input",
            str(request_path),
            "--ligand-input",
            str(request_path),
            "--result-json",
            str(result_path),
            "--manifest-json",
            str(manifest_path),
            "--evidence-bundle-json",
            str(evidence_bundle_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["request_mode"] == "request_json"
    assert payload["result"]["ok"] is True
    assert payload["claim_metadata"]["claim_safe"] is False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert verify_result_manifest(
        manifest,
        signing_key="local-dev-result-manifest-signing-key-change-me",
    )


def test_existing_runner_compatibility_hooks_call_canonical_service() -> None:
    payload = {
        "runner_profile_params": {
            "protein_input": MINI_PDB,
            "ligand_input": VALID_SMILES,
            "pose_count": 4,
            "top_k": 2,
            "stability_steps": 0,
        }
    }
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        run_tier_beta_vertical_slice_compat as backmapping_compat,
    )
    from betelgeuze_engine.product.runners.htvs_pipeline import (
        run_tier_beta_vertical_slice_compat as htvs_compat,
    )

    htvs_result = htvs_compat(payload)
    backmapping_result = backmapping_compat(payload)

    assert htvs_result.ok is True
    assert backmapping_result.ok is True
    assert htvs_result.typed_input["schema_version"] == "tier_beta_biodiscovery_screening_v1"
    assert backmapping_result.pose_scores[0]["pose_rank"] == 1


def test_tier_beta_runner_adapter_uses_versioned_typed_request() -> None:
    from betelgeuze_engine.product.runners.tier_beta_service_adapter import (
        RUNNER_ADAPTER_SCHEMA_VERSION,
        TierBetaRunnerRequest,
        parse_tier_beta_runner_payload,
    )

    request = parse_tier_beta_runner_payload(
        {
            "runner_profile_params": {
                "pdb_content": MINI_PDB,
                "smiles": VALID_SMILES,
                "pocket_residue_indices": ["1", 2],
                "pose_count": "4",
                "top_k": "2",
                "stability_steps": "",
                "seed": "9",
                "metadata": {"source": "unit"},
            }
        }
    )

    assert isinstance(request, TierBetaRunnerRequest)
    assert request.schema_version == RUNNER_ADAPTER_SCHEMA_VERSION
    assert request.protein_input == MINI_PDB
    assert request.ligand_input == VALID_SMILES
    assert request.pocket_residue_indices == [1, 2]
    assert request.pose_count == 4
    assert request.top_k == 2
    assert request.stability_steps == 0
    assert request.seed == 9
    assert request.metadata == {"source": "unit"}
    assert request.to_dict()["schema_version"] == RUNNER_ADAPTER_SCHEMA_VERSION


def test_stability_simulation_records_md_reproducibility_diagnostics() -> None:
    result = TierBetaScreening(device="cpu", pose_count=4, top_k=2, stability_steps=4, seed=7).screen(
        protein_input=MINI_PDB,
        ligand_input=VALID_SMILES,
    )

    assert result.ok is True
    stability = result.result_manifest["stability"]["diagnostics"]
    assert stability["steps_run"] == 4
    assert "energy_drift" in stability
    assert stability["constraints"]["coordinate_clamp_box_a"] > 0
    assert stability["pbc_enabled"] is False
    assert stability["thermostat"]["type"] == "langevin_proxy"
    assert stability["restart_reproducible"] is None
    assert stability["restart_seed"] == 7
