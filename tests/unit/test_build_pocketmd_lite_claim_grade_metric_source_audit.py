from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from tools.product import build_pocketmd_lite_claim_grade_metric_source_audit as mod


_INPUT_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "required_collection_metrics",
    "selected_trajectory_npz",
    "selected_trajectory_source",
    "selected_trajectory_readable",
    "selected_trajectory_claim_grade_metric_fields_present",
    "protein_structure_source_path",
    "protein_structure_source_path_available",
    "ligand_smiles",
    "ligand_smiles_present",
    "collection_input_ready",
    "claim_grade_metrics_already_present",
]


def _write_input_csv(path: Path, npz_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol",
                "required_collection_metrics": (
                    "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count"
                ),
                "selected_trajectory_npz": str(npz_path),
                "selected_trajectory_source": "exact_basename_restore_candidate",
                "selected_trajectory_readable": "true",
                "selected_trajectory_claim_grade_metric_fields_present": "false",
                "protein_structure_source_path": "protein.pdb",
                "protein_structure_source_path_available": "true",
                "ligand_smiles": "CCO",
                "ligand_smiles_present": "true",
                "collection_input_ready": "true",
                "claim_grade_metrics_already_present": "false",
            }
        )


def _write_probe_json(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_pocketmd_lite_metric_collection_probe_proxy_only"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_npz(
    path: Path,
    *,
    metric_fields: bool = False,
    protein_atom_frames: bool = False,
    ligand_atom_frames: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "protein_ca": np.asarray([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]], dtype=np.float32),
        "ligand_frames": np.asarray(
            [
                [[2.8, 0.0, 0.0], [4.4, 0.0, 0.0]],
                [[3.0, 0.0, 0.0], [4.6, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
        "frame_indices": np.asarray([0, 1], dtype=np.int32),
    }
    if metric_fields:
        payload["local_min_ligand_rmsd_a"] = np.asarray(1.1, dtype=np.float32)
        payload["hbond_persistence"] = np.asarray(0.75, dtype=np.float32)
        payload["initial_clash_count"] = np.asarray(2, dtype=np.int32)
    if protein_atom_frames:
        payload["protein_atom_frames"] = np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [5.0, 0.0, 0.0]],
                [[0.1, 0.0, 0.0], [1.1, 0.0, 0.0], [5.1, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )
    if ligand_atom_frames:
        payload["ligand_atom_frames"] = np.asarray(
            [
                [[2.8, 0.0, 0.0], [3.1, 0.0, 0.0], [4.4, 0.0, 0.0]],
                [[3.0, 0.0, 0.0], [3.3, 0.0, 0.0], [4.6, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )
    np.savez(path, **payload)


def test_audit_distinguishes_proxy_selected_from_partial_atomized_candidate(tmp_path: Path) -> None:
    selected = tmp_path / "selected" / "ADRB2_GPCR_BLIND__rep0001__carvedilol.npz"
    search_root = tmp_path / "search"
    partial = search_root / "ADRB2_GPCR_BLIND__rep9999__carvedilol.npz"
    input_csv = tmp_path / "input.csv"
    probe_json = tmp_path / "probe.json"
    _write_npz(selected)
    _write_npz(partial, protein_atom_frames=True)
    _write_input_csv(input_csv, selected)
    _write_probe_json(probe_json)

    payload = mod.build_pocketmd_lite_claim_grade_metric_source_audit(
        input_csv=input_csv,
        probe_json=probe_json,
        search_roots=[search_root],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pocketmd_lite_claim_grade_metric_source_partial_atomized"
    assert summary["candidate_count"] == 1
    assert summary["exact_metric_source_ready_count"] == 0
    assert summary["selected_proxy_only_count"] == 1
    assert summary["atomized_protein_source_candidate_count"] == 1
    assert summary["ligand_atom_source_candidate_count"] == 0
    assert summary["partial_atomized_protein_only_candidate_count"] == 1
    row = payload["rows"][0]
    assert row["selected_npz_status"] == "proxy_only_trajectory"
    assert row["best_candidate_status"] == "partial_atomized_protein_only"
    assert row["recommended_next_local_action"] == (
        "generate_or_recover_ligand_atom_frames_then_run_claim_grade_metric_collector"
    )


def test_audit_ready_when_selected_npz_contains_exact_metric_fields(tmp_path: Path) -> None:
    selected = tmp_path / "ADRB2_GPCR_BLIND__rep0001__carvedilol.npz"
    input_csv = tmp_path / "input.csv"
    probe_json = tmp_path / "probe.json"
    _write_npz(selected, metric_fields=True)
    _write_input_csv(input_csv, selected)
    _write_probe_json(probe_json)

    payload = mod.build_pocketmd_lite_claim_grade_metric_source_audit(
        input_csv=input_csv,
        probe_json=probe_json,
        search_roots=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "pocketmd_lite_claim_grade_metric_source_audit_ready"
    assert summary["exact_metric_source_ready_count"] == 1
    row = payload["rows"][0]
    assert row["selected_exact_metric_ready"] is True
    assert row["selected_missing_exact_metric_fields"] == []
    assert row["recommended_next_local_action"] == (
        "extract_exact_metric_fields_into_candidate_fill_preview_then_rerun_report"
    )


def test_main_writes_audit_artifacts(tmp_path: Path) -> None:
    selected = tmp_path / "ADRB2_GPCR_BLIND__rep0001__carvedilol.npz"
    input_csv = tmp_path / "input.csv"
    probe_json = tmp_path / "probe.json"
    out_json = tmp_path / "audit.json"
    out_md = tmp_path / "audit.md"
    out_csv = tmp_path / "audit.csv"
    _write_npz(selected)
    _write_input_csv(input_csv, selected)
    _write_probe_json(probe_json)

    rc = mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--probe-json",
            str(probe_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "pocketmd_lite_claim_grade_metric_source_audit"
    assert out_md.read_text(encoding="utf-8").startswith(
        "# PocketMD Lite Claim-Grade Metric Source Audit"
    )
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["entry_id"] == "ADRB2_GPCR_BLIND:carvedilol"
