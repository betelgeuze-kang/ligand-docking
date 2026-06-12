from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from tools import build_selected_allatom_visual_bundle as mod
from tools.wetlab import wetlab_selected_allatom_visual as visual_mod


def _write_pdb(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       4.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  SER A   3       0.000   4.000   0.000  1.00 20.00           C",
                "HETATM    4  C1  LIG X   1       1.500   1.000   0.000  1.00 20.00           C",
                "HETATM    5  C2  LIG X   1       2.000   1.300   0.200  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_npz(path: Path, *, protein_ca: np.ndarray, ligand_frames: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        protein_ca=np.asarray(protein_ca, dtype=np.float32),
        ligand_frames=np.asarray(ligand_frames, dtype=np.float32),
        frame_indices=np.arange(int(ligand_frames.shape[0]), dtype=np.int32),
    )


def _patch_dashboard(monkeypatch, root: Path) -> None:
    def _fake_dashboard(*, dashboard_csv: Path, target_id: str, pdb_paths: list[str], movie_json: Path, out_html: Path, out_json: Path):
        del dashboard_csv, target_id, pdb_paths, movie_json
        out_html.write_text("<html>selected-allatom visual bundle</html>", encoding="utf-8")
        out_json.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return {"movie_entries": 1, "root": str(root)}

    monkeypatch.setattr(mod, "_build_dashboard", _fake_dashboard)


def _patch_no_repo_native_registry(monkeypatch) -> None:
    monkeypatch.setattr(mod, "resolve_repo_native_entry", lambda _target_id: {})


def _base_payloads(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], Path]:
    pdb_path = tmp_path / "focus.pdb"
    _write_pdb(pdb_path)

    stage2_manifest_csv = tmp_path / "stage2_manifest.csv"
    _write_csv(
        stage2_manifest_csv,
        [
            {
                "queue_id": "queue-001",
                "target": "T. cruzi PDE",
                "ligand_id": "toy_ligand",
                "status": "ok_cached",
                "frames_written": 300,
                "trajectory_dir": str(tmp_path / "traj_dir"),
                "trajectory_npz": str(tmp_path / "traj_dir" / "toy_ligand.npz"),
            }
        ],
    )
    _write_npz(
        tmp_path / "traj_dir" / "toy_ligand.npz",
        protein_ca=np.asarray(
            [
                [0.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
                [0.0, 4.0, 0.0],
            ],
            dtype=np.float32,
        ),
        ligand_frames=np.asarray(
            [
                [[1.5, 1.0, 0.0], [2.0, 1.3, 0.2]],
                [[7.5, 7.0, 0.0], [8.0, 7.3, 0.2]],
            ],
            dtype=np.float32,
        ),
    )

    review_packet = {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_review_packet_ready",
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_review_packet",
        },
        "rows": [
            {
                "packet_rank": 1,
                "ligand_id": "toy_ligand",
                "compound_name": "Toy Ligand",
                "compound_name_human_readable": "Toy Ligand",
                "backmapped_pdb": str(pdb_path),
                "mean_min_distance_A": 2.71,
                "contact_fraction": 0.72,
                "binding_energy_proxy": -0.12,
                "stability_score": 0.44,
                "trajectory_frames": 300,
                "selection_score_value": -7.1,
                "commercial_overall_score_v2": 55.8,
                "commercial_confidence_score_v2": 61.0,
                "commercial_soft_score_v2": 53.0,
                "commercial_risk_bucket_v2": "high",
                "commercial_decision_class_v2": "commercial_review_only",
                "translation_gate_status": "fail",
                "translation_gate_reason": "mean_min_distance_A_too_high",
                "shortlist_tier": "defer",
                "recommended_next_expensive_lane": "defer_expensive_lane",
                "recommended_next_expensive_lane_reason": "translation gate still fails",
                "recommended_next_expensive_lane_action": "re_minimize_then_short_replicated_md",
                "recommended_next_expensive_lane_action_codes": [
                    "recompute_mean_min_distance_A",
                    "short_replicated_md_consensus",
                ],
                "recommended_next_expensive_lane_blocker_codes": [
                    "mean_min_distance_A_fail",
                ],
            }
        ],
    }
    lane_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_rescue_lane_ready",
            "base_stage2_manifest_csv": str(stage2_manifest_csv),
        }
    }
    runner_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_rescue_ready",
            "allatom_stage2_manifest_csv": str(stage2_manifest_csv),
        }
    }
    retry_handoff = {
        "summary": {
            "selected_allatom_target_id": "T. cruzi PDE",
            "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
        }
    }
    return retry_handoff, review_packet, lane_payload, runner_payload, pdb_path


def test_build_selected_allatom_visual_bundle_manifest_contract(tmp_path: Path, monkeypatch) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)
    _patch_no_repo_native_registry(monkeypatch)

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=False,
        viewer_engine="3dmol",
    )

    summary = payload["summary"]
    structured = payload["structured"]
    rows = payload["rows"]

    assert summary["status"] == "selected_allatom_visual_bundle_ready"
    assert summary["visual_bundle_manifest_version"] == mod.VISUAL_BUNDLE_MANIFEST_VERSION
    assert summary["topk_requested"] == 1
    assert summary["topk_count"] == 1
    assert summary["selected_lane_json"].endswith("/lane.json")
    assert summary["selected_runner_json"].endswith("/runner.json")
    assert summary["hero_ligand_id"] == "toy_ligand"
    assert summary["primary_backmapped_pdb"] == str(pdb_path)
    assert summary["binding_event_candidate_count"] == 1
    assert summary["visual_pipeline_status"] == "not_run"
    assert summary["visual_pipeline_ok"] is False
    assert summary["primary_viewer_reference_pdb_ready"] is True
    assert summary["primary_protein_reference_structure_ready"] is False
    assert summary["primary_render_structure_kind"] == "viewer_reference_pdb"
    assert structured["feature_csv"].endswith("selected_allatom_visual_dashboard.csv")
    assert structured["source_stage2_manifest_csv"].endswith("stage2_manifest.csv")
    assert Path(structured["feature_csv"]).exists()

    assert len(rows) == 1
    assert rows[0]["trajectory_npz"].endswith("toy_ligand.npz")
    assert rows[0]["trajectory_dir"].endswith("traj_dir")
    assert rows[0]["viewer_reference_pdb"].endswith("_viewer_reference.pdb")
    assert rows[0]["viewer_reference_pdb_ready"] is True
    assert rows[0]["viewer_reference_frame_index"] == 0
    assert rows[0]["viewer_reference_trajectory_index"] == 0
    assert rows[0]["protein_reference_alignment_mode"] == "viewer_reference_pdb_direct"
    assert rows[0]["render_structure_path"] == rows[0]["viewer_reference_pdb"]
    assert rows[0]["render_structure_kind"] == "viewer_reference_pdb"
    assert rows[0]["render_structure_contains_protein"] is True
    assert rows[0]["binding_event_clip_status"] == "trajectory_npz_available"
    assert rows[0]["binding_event_clip_recipe_kind"] == "trajectory_npz_plus_backmapped_pdb"
    assert rows[0]["recommended_next_expensive_lane_action_codes_text"] == "recompute_mean_min_distance_A, short_replicated_md_consensus"
    assert rows[0]["recommended_next_expensive_lane_blocker_codes_text"] == "mean_min_distance_A_fail"
    assert rows[0]["turntable_movie_script_path"].endswith(".cxc")
    assert rows[0]["turntable_script_ready"] is True
    assert rows[0]["turntable_mp4_ready"] is False
    assert rows[0]["turntable_asset_status"] == "turntable_script_ready"
    assert rows[0]["turntable_asset_recommendation"] == "render_turntable_mp4"
    assert rows[0]["turntable_movie_mp4_path"] == ""
    assert summary["turntable_script_ready_count"] == 1
    assert summary["turntable_mp4_ready_count"] == 0


def test_build_selected_allatom_visual_bundle_visual_polish_artifacts(tmp_path: Path, monkeypatch) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)
    _patch_no_repo_native_registry(monkeypatch)

    def _fake_visual_polish(args):
        processed_dir = Path(args.processed_internal_dir)
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_pdb = processed_dir / f"visual_post_{pdb_path.name}"
        processed_pdb.write_text("MODEL\nENDMDL\n", encoding="utf-8")
        script_path = processed_dir / "hero.cxc"
        script_path.write_text("movie record\n", encoding="utf-8")
        mp4_path = processed_dir / "hero.mp4"
        mp4_path.write_bytes(b"mp4")
        refined_summary_json = Path(args.refined_summary_json)
        refined_summary_json.write_text(
            json.dumps({"rows": [{"source_path": str(pdb_path), "out_path": str(processed_pdb)}]}),
            encoding="utf-8",
        )
        chimerax_summary_json = Path(args.chimerax_summary_json)
        chimerax_summary_json.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "pdb_path": str(processed_pdb),
                            "script_path": str(script_path),
                            "mp4_path": str(mp4_path),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        Path(args.dashboard_html).write_text("<html>visual polish</html>", encoding="utf-8")
        Path(args.dashboard_json).write_text(json.dumps({"rows": 1}), encoding="utf-8")
        Path(args.out_summary_json).write_text(json.dumps({"ok": True}), encoding="utf-8")
        return {
            "ok": True,
            "artifacts": {
                "processed_internal_dir": str(processed_dir),
                "dashboard_html": str(args.dashboard_html),
                "dashboard_json": str(args.dashboard_json),
                "refined_summary_json": str(refined_summary_json),
                "refined_report_csv": str(args.refined_report_csv),
                "chimerax_summary_json": str(chimerax_summary_json),
                "chimerax_report_csv": str(args.chimerax_report_csv),
                "chimerax_out_dir": str(Path(args.chimerax_summary_json).parent),
                "out_summary_json": str(args.out_summary_json),
            },
        }

    monkeypatch.setattr(mod.visual_polish_mod, "run", _fake_visual_polish)

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=True,
        viewer_engine="3dmol",
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    visual = visual_mod.resolve_selected_allatom_visual_bundle(payload)

    assert summary["visual_pipeline_status"] == "ready"
    assert summary["visual_pipeline_ok"] is True
    assert row["visual_polish_processed_pdb"].endswith(f"visual_post_{pdb_path.name}")
    assert row["visual_polish_turntable_movie_script_path"].endswith("hero.cxc")
    assert row["visual_polish_turntable_movie_mp4_path"].endswith("hero.mp4")
    assert row["visual_polish_turntable_script_ready"] is True
    assert row["visual_polish_turntable_mp4_ready"] is True
    assert row["viewer_reference_pdb_ready"] is True
    assert row["render_structure_kind"] == "viewer_reference_pdb"
    assert visual["manifest_version"] == mod.VISUAL_BUNDLE_MANIFEST_VERSION
    assert visual["hero_ligand_id"] == "toy_ligand"
    assert visual["primary_binding_event_clip_status"] == "trajectory_npz_available"
    assert visual["primary_visual_polish_processed_pdb"].endswith(f"visual_post_{pdb_path.name}")


def test_build_selected_allatom_visual_bundle_prefers_protein_backmap_when_scorer_provenance_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)
    _patch_no_repo_native_registry(monkeypatch)

    protein_native = tmp_path / "native_reference.pdb"
    _write_pdb(protein_native)
    score_json = tmp_path / "score_payload.json"
    score_json.write_text(
        json.dumps(
            {
                "protein_structure_provenance": {
                    "source_path": str(protein_native),
                    "source_kind": "explicit_native_pdb",
                    "source_format": "pdb",
                    "source_available": True,
                    "source_residue_anchor_mode": "ca_only",
                    "notes": "explicit native protein reference",
                },
                "backmap_stats": {
                    "protein_residues": 2,
                    "protein_atoms": 10,
                    "ligand_atoms": 2,
                },
                "backmapped_contains_protein": True,
                "backmapped_structure_kind": "pseudo_backmapped_protein_ligand_pdb",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    scores_csv = tmp_path / "scores.csv"
    _write_csv(
        scores_csv,
        [
            {
                "ligand_id": "toy_ligand",
                "backmapped_pdb": str(pdb_path),
                "score_json": str(score_json),
                "protein_structure_source_path": str(protein_native),
                "protein_structure_source_kind": "explicit_native_pdb",
                "protein_structure_source_format": "pdb",
                "protein_structure_source_available": True,
                "backmapped_contains_protein": True,
                "backmapped_structure_kind": "pseudo_backmapped_protein_ligand_pdb",
            }
        ],
    )
    runner_payload["summary"]["allatom_scores_csv"] = str(scores_csv)

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=False,
        viewer_engine="3dmol",
    )

    row = payload["rows"][0]
    summary = payload["summary"]

    assert row["protein_reference_structure_path"] == str(protein_native)
    assert row["protein_reference_structure_ready"] is True
    assert row["protein_reference_structure_aligned_for_viewer"] is True
    assert row["protein_reference_provenance"] == "explicit_native_pdb"
    assert row["protein_reference_alignment_mode"] == "viewer_reference_kabsch"
    assert row["render_structure_path"].endswith("toy_ligand_native_aligned_reference.pdb")
    assert row["render_structure_kind"] == "protein_reference_aligned_viewer_pdb"
    assert row["render_structure_contains_protein"] is True
    assert "Aligned native protein to viewer reference" in row["protein_reference_alignment_note"]
    assert "REMARK SELECTED_ALLATOM_ALIGNMENT_MODE viewer_reference_kabsch" in Path(
        row["render_structure_path"]
    ).read_text(encoding="utf-8")
    assert summary["primary_protein_reference_structure_path"] == str(protein_native)
    assert summary["primary_protein_reference_aligned_viewer_ready"] is True
    assert summary["primary_protein_reference_alignment_mode"] == "viewer_reference_kabsch"


def test_build_selected_allatom_visual_bundle_falls_back_to_unaligned_overlay_when_native_is_ready_but_alignment_is_not(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)
    _patch_no_repo_native_registry(monkeypatch)

    protein_only_native = tmp_path / "protein_only_native.pdb"
    protein_only_native.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       5.000   5.000   5.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       8.000   5.000   5.000  1.00 20.00           C",
                "ATOM      3  CA  SER A   3      11.000   7.000   5.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    native_csv = tmp_path / "rescue_target_native.csv"
    _write_csv(
        native_csv,
        [
            {
                "target": "TcrPDEC1",
                "native_pdb_path": str(protein_only_native),
                "pdb_id": "3V94",
                "notes": "protein-only native without ligand anchor",
                "target_aliases": "T. cruzi PDE;t_cruzi_pde;TcrPDEC1",
            }
        ],
    )
    lane_payload["summary"]["rescue_target_native_csv"] = str(native_csv)
    runner_payload["summary"]["rescue_target_native_csv"] = str(native_csv)
    stage2_npz = tmp_path / "traj_dir" / "toy_ligand.npz"
    _write_npz(
        stage2_npz,
        protein_ca=np.zeros((1, 3), dtype=np.float32),
        ligand_frames=np.asarray(
            [
                [[1.0, 1.0, 0.0], [1.5, 1.2, 0.1]],
                [[1.2, 0.8, 0.0], [1.7, 1.1, 0.1]],
            ],
            dtype=np.float32,
        ),
    )

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=False,
        viewer_engine="3dmol",
    )

    row = payload["rows"][0]
    summary = payload["summary"]

    assert row["protein_reference_structure_path"] == str(protein_only_native)
    assert row["viewer_protein_context_quality_gate_pass"] is False
    assert row["viewer_protein_context_reason"] == "protein_ca_count_lt_3"
    assert row["protein_reference_alignment_mode"] == "missing_anchor_for_translation"
    assert row["protein_reference_aligned_viewer_ready"] is False
    assert row["protein_reference_viewer_mode"] == "unaligned_overlay"
    assert row["render_structure_path"] == str(pdb_path)
    assert row["render_structure_contains_protein"] is False
    assert summary["primary_protein_reference_viewer_mode"] == "unaligned_overlay"
    assert summary["primary_viewer_protein_context_quality_gate_pass"] is False


def test_build_selected_allatom_visual_bundle_aligns_native_reference_from_ligand_only_viewer_pose(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, _pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)

    native_complex = tmp_path / "native_complex.pdb"
    native_complex.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       3.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  SER A   3       0.000   3.000   0.000  1.00 20.00           C",
                "HETATM    4  C1  LIG L   1       1.000   1.000   0.000  1.00 20.00           C",
                "HETATM    5  C2  LIG L   1       1.500   1.300   0.200  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    native_csv = tmp_path / "rescue_target_native.csv"
    _write_csv(
        native_csv,
        [
            {
                "target": "T. cruzi PDE",
                "native_pdb_path": str(native_complex),
                "pdb_id": "3V94",
                "notes": "native complex with ligand anchor",
                "target_aliases": "t_cruzi_pde;TcrPDEC1",
            }
        ],
    )
    lane_payload["summary"]["rescue_target_native_csv"] = str(native_csv)
    runner_payload["summary"]["rescue_target_native_csv"] = str(native_csv)
    stage2_npz = tmp_path / "traj_dir" / "toy_ligand.npz"
    _write_npz(
        stage2_npz,
        protein_ca=np.zeros((1, 3), dtype=np.float32),
        ligand_frames=np.asarray(
            [
                [[9.0, 4.0, 0.0], [9.5, 4.3, 0.2]],
                [[9.2, 4.1, 0.0], [9.7, 4.4, 0.2]],
            ],
            dtype=np.float32,
        ),
    )

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=False,
        viewer_engine="3dmol",
    )

    row = payload["rows"][0]
    summary = payload["summary"]

    assert row["viewer_protein_context_quality_gate_pass"] is False
    assert row["viewer_pose_pdb_ready"] is True
    assert row["protein_reference_alignment_mode"] == "native_ligand_centroid_translation"
    assert row["protein_reference_aligned_viewer_ready"] is True
    assert row["protein_reference_viewer_mode"] == "aligned_replace"
    assert row["render_structure_kind"] == "protein_reference_aligned_viewer_pdb"
    assert row["render_structure_contains_protein"] is True
    assert summary["primary_viewer_pose_pdb_ready"] is True
    assert summary["primary_protein_reference_alignment_mode"] == "native_ligand_centroid_translation"


def test_build_selected_allatom_visual_bundle_uses_alias_matched_target_native_csv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_handoff, review_packet, lane_payload, runner_payload, _pdb_path = _base_payloads(tmp_path)
    _patch_dashboard(monkeypatch, tmp_path)
    _patch_no_repo_native_registry(monkeypatch)

    native_dir = tmp_path / "lane_artifacts"
    native_dir.mkdir(parents=True, exist_ok=True)
    protein_native = native_dir / "t_cruzi_native.pdb"
    _write_pdb(protein_native)
    _write_csv(
        native_dir / "target_native_stub.csv",
        [
            {
                "target": "t_cruzi_pde",
                "native_pdb_path": str(protein_native),
                "pdb_id": "1TCP",
                "notes": "lane-local alias-matched native reference",
                "pocket_x": "1.0",
                "pocket_y": "2.0",
                "pocket_z": "3.0",
            }
        ],
    )
    lane_payload["summary"]["trajectory_root"] = str(native_dir / "traj_run")

    payload = mod.build_payload(
        retry_handoff_payload=retry_handoff,
        review_packet_payload=review_packet,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        review_packet_json=str(tmp_path / "review_packet.json"),
        lane_json=str(tmp_path / "lane.json"),
        runner_json=str(tmp_path / "runner.json"),
        top_k=1,
        assets_root=str(tmp_path / "bundle_assets"),
        run_visual_pipeline=False,
        viewer_engine="3dmol",
    )

    row = payload["rows"][0]
    summary = payload["summary"]

    assert row["protein_reference_provenance"] == "target_native_csv"
    assert row["protein_reference_structure_path"] == str(protein_native)
    assert row["protein_reference_structure_ready"] is True
    assert row["protein_reference_pdb_id"] == "1TCP"
    assert row["protein_reference_notes"] == "lane-local alias-matched native reference"
    assert row["protein_reference_alignment_mode"] == "viewer_reference_kabsch"
    assert row["render_structure_kind"] == "protein_reference_aligned_viewer_pdb"
    assert row["protein_reference_aligned_viewer_path"].endswith("_native_aligned_reference.pdb")
    assert summary["primary_protein_reference_structure_path"] == str(protein_native)
    assert summary["primary_protein_reference_aligned_viewer_ready"] is True
