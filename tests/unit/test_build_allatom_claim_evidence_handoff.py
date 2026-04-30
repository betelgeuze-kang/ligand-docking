import json
from pathlib import Path

import numpy as np

from tools import build_allatom_claim_evidence_handoff as mod


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _valid_strict_summary() -> dict:
    return {
        "summary": {"targets": 2},
        "gates": {
            "accuracy_gate": {
                "avg_neighbor_jaccard": 0.98,
                "avg_e2e_rmse_raw": 0.12,
                "avg_e2e_rel_rmse_mean_clipped": 0.04,
            },
            "speed": {"avg_speedup_on_vs_off": 3.1},
            "long_stability": {"passed_targets": 2},
        },
    }


def _parse_args(tmp_path: Path, *extra: str):
    return mod.build_parser().parse_args(
        [
            "--repair-packet-json",
            str(tmp_path / "repair.json"),
            "--accuracy-gate-json",
            str(tmp_path / "preflight.json"),
            "--accuracy-gate-csv",
            str(tmp_path / "preflight.csv"),
            "--target-registration-json",
            str(tmp_path / "registration.json"),
            "--out-json",
            str(tmp_path / "handoff.json"),
            "--out-md",
            str(tmp_path / "handoff.md"),
            *extra,
        ]
    )


def _strict_release_command(summary: dict) -> str:
    return next(
        cmd
        for cmd in summary["recommended_commands"]
        if "run_openmm_2bead_strict_release.py" in cmd
    )


def test_ready_when_valid_strict_summary_and_accuracy_external_csv(tmp_path):
    strict_json = tmp_path / "strict_summary.json"
    accuracy_csv = tmp_path / "accuracy_external.csv"
    _write_json(strict_json, _valid_strict_summary())
    accuracy_csv.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\n"
        "T. cruzi PDE,1.2,1.1\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(accuracy_csv),
        )
    )

    summary = payload["summary"]
    assert summary["strict_summary_status"] == "ready"
    assert summary["accuracy_external_status"] == "ready"
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_summary_generation_ready"] is False
    assert summary["claim_readiness_ready"] is True
    assert summary["missing_inputs"] == []
    assert summary["upstream_missing_inputs"] == ["strict_release_external_manifest_csv"]
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_release_unsupported_targets"] == []
    assert payload["inputs"]["strict_summary_json"]["ready"] is True
    assert payload["inputs"]["accuracy_external_csv"]["ready"] is True
    strict_release_command = _strict_release_command(summary)
    assert "--external-manifest" in strict_release_command
    assert "--manifest-csv" not in strict_release_command
    assert "<external_openmm_manifest.csv>" in strict_release_command
    assert Path(payload["artifacts"]["json"]).exists()
    assert Path(payload["artifacts"]["md"]).exists()


def test_target_registration_packet_is_surfaced_as_handoff_context(tmp_path):
    registration_json = tmp_path / "registration.json"
    _write_json(
        registration_json,
        {
            "summary": {
                "status": "blocked",
                "registration_ready": False,
                "blockers": [
                    "research_constants_target_missing",
                    "long_stability_profile_target_missing",
                ],
                "canonical_chain_ready": True,
                "next_required_step": "Register T. cruzi PDE with canonical_chain=B and n_res=334.",
            },
            "strict_release_registry": {
                "canonical_chain": "B",
                "selected_chain_ca_count": 334,
                "selected_chain_seqres_count": 345,
                "recommended_canonical_chain": "B",
            },
        },
    )

    payload = mod.run_build(_parse_args(tmp_path))

    summary = payload["summary"]
    registration_input = payload["inputs"]["target_registration_packet"]
    assert summary["target_registration_status"] == "blocked"
    assert summary["target_registration_blockers"] == [
        "research_constants_target_missing",
        "long_stability_profile_target_missing",
    ]
    assert summary["target_registration_canonical_chain_ready"] is True
    assert registration_input["ready"] is False
    assert registration_input["path"] == str(registration_json)
    assert registration_input["canonical_chain"] == "B"
    assert registration_input["selected_chain_ca_count"] == 334


def test_preflight_csv_columns_are_blocked_as_accuracy_external(tmp_path):
    strict_json = tmp_path / "strict_summary.json"
    preflight_csv = tmp_path / "preflight.csv"
    _write_json(strict_json, _valid_strict_summary())
    preflight_csv.write_text(
        "target,avg_neighbor_jaccard,avg_e2e_rmse_raw,avg_e2e_rel_rmse_mean_clipped\n"
        "T. cruzi PDE,0.98,0.12,0.04\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(preflight_csv),
        )
    )

    summary = payload["summary"]
    assert summary["accuracy_external_status"] == "blocked"
    assert summary["claim_readiness_ready"] is False
    assert "accuracy_external_csv" in summary["missing_inputs"]
    assert "strict_release_external_manifest_csv" in summary["upstream_missing_inputs"]
    reason = payload["inputs"]["accuracy_external_csv"]["reason"]
    assert reason == "missing_accuracy_external_columns:avg_rmsd_aligned,avg_rmsd_vs_native_aligned"


def test_rescue_state_like_json_is_blocked_as_strict_summary(tmp_path):
    rescue_json = tmp_path / "rescue_state.json"
    accuracy_csv = tmp_path / "accuracy_external.csv"
    _write_json(
        rescue_json,
        {
            "summary": {"status": "rescue_state", "targets": 1},
            "state": {"attempt": 3},
        },
    )
    accuracy_csv.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\n"
        "T. cruzi PDE,1.2,1.1\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--strict-summary-json",
            str(rescue_json),
            "--accuracy-external-csv",
            str(accuracy_csv),
        )
    )

    summary = payload["summary"]
    assert summary["strict_summary_status"] == "blocked"
    assert summary["accuracy_external_status"] == "ready"
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_summary_generation_ready"] is False
    assert summary["claim_readiness_ready"] is False
    assert "strict_summary_json" in summary["missing_inputs"]
    assert "strict_release_external_manifest_csv" in summary["upstream_missing_inputs"]
    assert payload["inputs"]["strict_summary_json"]["reason"] == "missing_gates"


def test_strict_release_external_manifest_is_validated_separately(tmp_path):
    strict_json = tmp_path / "strict_summary.json"
    accuracy_csv = tmp_path / "accuracy_external.csv"
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "chignolin.npy"
    np.save(coords, np.zeros((10, 3), dtype=np.float32))
    _write_json(strict_json, _valid_strict_summary())
    accuracy_csv.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\n"
        "T. cruzi PDE,1.2,1.1\n",
        encoding="utf-8",
    )
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Chignolin,{coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(accuracy_csv),
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    target_input = payload["inputs"]["strict_release_target_support"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "ready"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_release_targets_supported"] is True
    assert summary["strict_release_unsupported_targets"] == []
    assert summary["strict_summary_generation_ready"] is True
    assert summary["upstream_missing_inputs"] == []
    assert manifest_input["ready"] is True
    assert manifest_input["path"] == str(strict_manifest)
    assert target_input["ready"] is True
    assert target_input["unsupported_targets"] == []
    strict_release_command = _strict_release_command(payload["summary"])
    assert f"--external-manifest {strict_manifest}" in strict_release_command
    assert "--targets Chignolin" in strict_release_command
    assert "blocked:" not in strict_release_command


def test_claim_input_manifest_is_not_used_as_strict_release_external_manifest(tmp_path):
    repair_json = tmp_path / "repair.json"
    claim_manifest = tmp_path / "allatom_rescue_stage2_manifest.csv"
    claim_manifest.write_text(
        "target,trajectory_npz\n"
        "T. cruzi PDE,/tmp/tcruzi.npz\n",
        encoding="utf-8",
    )
    _write_json(
        repair_json,
        {
            "summary": {
                "claim_equivalence_available_inputs": {
                    "openmm_manifest_csv": str(claim_manifest),
                }
            }
        },
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--repair-packet-json",
            str(repair_json),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_summary_generation_ready"] is False
    assert summary["upstream_missing_inputs"] == ["strict_release_external_manifest_csv"]
    assert manifest_input["ready"] is False
    assert manifest_input["reason"] == "missing_strict_release_external_manifest_columns:path"
    strict_release_command = _strict_release_command(payload["summary"])
    assert "<external_openmm_manifest.csv>" in strict_release_command
    assert str(claim_manifest) not in strict_release_command


def test_missing_strict_summary_reports_strict_release_manifest_as_upstream_prerequisite(tmp_path):
    accuracy_csv = tmp_path / "accuracy_external.csv"
    accuracy_csv.write_text(
        "target,avg_rmsd_aligned,avg_rmsd_vs_native_aligned\n"
        "T. cruzi PDE,1.2,1.1\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--accuracy-external-csv",
            str(accuracy_csv),
        )
    )

    summary = payload["summary"]
    assert summary["strict_summary_status"] == "blocked"
    assert summary["accuracy_external_status"] == "ready"
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_summary_generation_ready"] is False
    assert summary["missing_inputs"] == ["strict_summary_json"]
    assert summary["upstream_missing_inputs"] == ["strict_release_external_manifest_csv"]
    strict_release_command = _strict_release_command(summary)
    assert "--external-manifest <external_openmm_manifest.csv>" in strict_release_command


def test_default_tcruzi_target_with_valid_strict_manifest_is_ready_for_strict_summary_generation(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "tcruzi.npy"
    np.save(coords, np.zeros((334, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine\n"
        f"T. cruzi PDE,{coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    summary = payload["summary"]
    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    assert summary["strict_release_external_manifest_status"] == "ready"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_release_targets_supported"] is True
    assert summary["strict_release_unsupported_targets"] == []
    assert summary["strict_summary_generation_ready"] is True
    assert summary["upstream_missing_inputs"] == []
    assert manifest_input["ready"] is True
    strict_release_command = _strict_release_command(summary)
    assert f"--external-manifest {strict_manifest}" in strict_release_command
    assert "--targets 'T. cruzi PDE'" in strict_release_command
    assert "blocked:" not in strict_release_command


def test_supported_target_with_valid_strict_manifest_is_ready_for_strict_summary_generation(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "chignolin.npy"
    np.save(coords, np.zeros((10, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Chignolin,{coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    target_input = payload["inputs"]["strict_release_target_support"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "ready"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_release_targets_supported"] is True
    assert summary["strict_release_unsupported_targets"] == []
    assert summary["strict_summary_generation_ready"] is True
    assert summary["upstream_missing_inputs"] == []
    assert manifest_input["ready"] is True
    assert target_input["ready"] is True
    assert target_input["supported_targets"] == ["Chignolin"]
    strict_release_command = _strict_release_command(summary)
    assert f"--external-manifest {strict_manifest}" in strict_release_command
    assert "--targets Chignolin" in strict_release_command
    assert "blocked:" not in strict_release_command


def test_valid_manifest_for_different_target_is_not_coverage_ready(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "trp_cage.npy"
    np.save(coords, np.zeros((20, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Trp_Cage,{coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_summary_generation_ready"] is False
    assert manifest_input["valid_targets"] == ["Trp_Cage"]
    assert manifest_input["missing_targets"] == ["Chignolin"]
    assert manifest_input["unexpected_targets"] == ["Trp_Cage"]
    assert "missing_strict_release_manifest_targets:Chignolin" in manifest_input["reason"]
    assert "unexpected_strict_release_manifest_targets:Trp_Cage" in manifest_input["reason"]
    strict_release_command = _strict_release_command(summary)
    assert "<external_openmm_manifest.csv>" in strict_release_command
    assert str(strict_manifest) not in strict_release_command


def test_valid_manifest_missing_one_requested_target_is_not_coverage_ready(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "chignolin.npy"
    np.save(coords, np.zeros((10, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Chignolin,{coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin,Trp_Cage",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_summary_generation_ready"] is False
    assert manifest_input["valid_targets"] == ["Chignolin"]
    assert manifest_input["missing_targets"] == ["Trp_Cage"]
    assert manifest_input["unexpected_targets"] == []
    assert "missing_strict_release_manifest_targets:Trp_Cage" in manifest_input["reason"]
    strict_release_command = _strict_release_command(summary)
    assert "<external_openmm_manifest.csv>" in strict_release_command
    assert str(strict_manifest) not in strict_release_command


def test_supported_target_with_missing_strict_manifest_file_is_blocked(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    missing_coords = tmp_path / "missing_chignolin.npy"
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Chignolin,{missing_coords},openmm\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_summary_generation_ready"] is False
    assert "missing_file" in manifest_input["reason"]
    assert "missing_file" in manifest_input["rejected_candidates"][0]["reason"]
    strict_release_command = _strict_release_command(summary)
    assert "<external_openmm_manifest.csv>" in strict_release_command
    assert str(strict_manifest) not in strict_release_command


def test_supported_target_with_bad_engine_is_blocked(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "chignolin.npy"
    np.save(coords, np.zeros((10, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine\n"
        f"Chignolin,{coords},template\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_summary_generation_ready"] is False
    assert "engine_not_md" in manifest_input["reason"]
    assert "engine_not_md" in manifest_input["rejected_candidates"][0]["reason"]


def test_supported_target_with_ca_sc_2bead_atom_mismatch_is_blocked(tmp_path):
    strict_manifest = tmp_path / "external_manifest.csv"
    coords = tmp_path / "chignolin.npy"
    np.save(coords, np.zeros((10, 3), dtype=np.float32))
    strict_manifest.write_text(
        "target,path,engine,representation\n"
        f"Chignolin,{coords},openmm,ca_sc_2bead\n",
        encoding="utf-8",
    )

    payload = mod.run_build(
        _parse_args(
            tmp_path,
            "--targets",
            "Chignolin",
            "--strict-release-external-manifest",
            str(strict_manifest),
        )
    )

    manifest_input = payload["inputs"]["strict_release_external_manifest_csv"]
    summary = payload["summary"]
    assert summary["strict_release_external_manifest_status"] == "blocked"
    assert summary["strict_release_target_status"] == "ready"
    assert summary["strict_summary_generation_ready"] is False
    assert "n_atoms_mismatch" in manifest_input["reason"]
    assert "n_atoms_mismatch" in manifest_input["rejected_candidates"][0]["reason"]
