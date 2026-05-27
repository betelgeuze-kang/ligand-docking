from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_identity_seed_clearance_workorder as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(path: Path, *, residue: str = "ALA", x: float = 1.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"ATOM      1  CA  {residue} A   1       {x:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00 20.00           C\n",
        encoding="utf-8",
    )
    return str(path)


def _seed_inventory(tmp_path: Path, prediction: str, native: str) -> Path:
    path = tmp_path / "seed_inventory.json"
    _write_json(
        path,
        {
            "summary": {"seed_inventory_status": "batch_seed_shape_ready_operator_clearance_required"},
            "rows": [
                {
                    "seed_rank": 1,
                    "batch_slot": 1,
                    "seed_status": "operator_clearance_required",
                    "scope": "monomer",
                    "benchmark_id": "hist_seed_bba5",
                    "target_id": "HIST_BBA5",
                    "prediction_pdb": prediction,
                    "native_pdb": native,
                }
            ],
        },
    )
    return path


def _args(tmp_path: Path, seed_inventory: Path, *extra: str) -> list[str]:
    return [
        "--seed-inventory-json",
        str(seed_inventory),
        "--operator-clearance-csv",
        str(tmp_path / "operator_clearance.csv"),
        "--out-json",
        str(tmp_path / "workorder.json"),
        "--out-csv",
        str(tmp_path / "workorder.csv"),
        "--out-md",
        str(tmp_path / "WORKORDER.md"),
        "--out-cleared-manifest-csv",
        str(tmp_path / "cleared_manifest.csv"),
        *extra,
    ]


def test_seed_clearance_workorder_creates_template_and_waits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    prediction = _pdb(tmp_path / "prediction.pdb")
    native = _pdb(tmp_path / "native.pdb", residue="GLY", x=4.0)
    seed_inventory = _seed_inventory(tmp_path, prediction, native)
    args = mod.parse_args(_args(tmp_path, seed_inventory))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["seed_clearance_status"] == "awaiting_seed_clearance"
    assert payload["summary"]["template_status"] == "created"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["ready_seed_count"] == 0
    assert payload["summary"]["phase_open_counts"]["no_leak_provenance"] == 1
    assert payload["summary"]["phase_open_counts"]["calibration"] == 1
    assert payload["summary"]["phase_open_counts"]["ablation"] == 1
    assert (tmp_path / "operator_clearance.csv").is_file()
    assert (tmp_path / "WORKORDER.md").is_file()


def test_seed_clearance_workorder_emits_cleared_manifest_for_complete_row(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    prediction = _pdb(tmp_path / "prediction.pdb")
    native = _pdb(tmp_path / "native.pdb", residue="GLY", x=4.0)
    seed_inventory = _seed_inventory(tmp_path, prediction, native)
    evidence = tmp_path / "evidence.md"
    evidence.write_text("HIST_BBA5 completed no-leak operator review.\n", encoding="utf-8")
    ablation = tmp_path / "ablation_manifest.csv"
    _write_csv(ablation, [{"layer": "recursive", "path": "prediction.pdb"}])
    _write_csv(
        tmp_path / "operator_clearance.csv",
        [
            {
                "seed_rank": "1",
                "batch_slot": "1",
                "benchmark_id": "hist_seed_bba5",
                "target_id": "HIST_BBA5",
                "scope": "monomer",
                "prediction_pdb": prediction,
                "native_pdb": native,
                "no_leak_evidence_ref": str(evidence),
                "leakage_clearance": "no_leak",
                "operator_clearance": "cleared",
                "operator": "operator-a",
                "prediction_created_at": "2026-01-01",
                "native_release_date": "2026-02-01",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.8",
                "best_native_metric": "0.9",
                "selected_score": "10.0",
                "best_score": "11.0",
                "ablation_manifest_ref": str(ablation),
                "notes": "complete",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, seed_inventory))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["seed_clearance_status"] == "ready_for_cleared_seed_manifest"
    assert payload["summary"]["ready_seed_count"] == 1
    assert payload["summary"]["cleared_manifest_row_count"] == 1
    assert payload["cleared_manifest_rows"][0]["target_id"] == "HIST_BBA5"


def test_seed_clearance_workorder_blocks_request_template_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    prediction = _pdb(tmp_path / "prediction.pdb")
    native = _pdb(tmp_path / "native.pdb", residue="GLY", x=4.0)
    seed_inventory = _seed_inventory(tmp_path, prediction, native)
    evidence = tmp_path / "evidence.md"
    evidence.write_text("CLEARANCE_EVIDENCE_STATUS: request_template for HIST_BBA5\n", encoding="utf-8")
    ablation = tmp_path / "ablation_manifest.csv"
    _write_csv(ablation, [{"layer": "recursive", "path": "prediction.pdb"}])
    _write_csv(
        tmp_path / "operator_clearance.csv",
        [
            {
                "seed_rank": "1",
                "batch_slot": "1",
                "benchmark_id": "hist_seed_bba5",
                "target_id": "HIST_BBA5",
                "scope": "monomer",
                "prediction_pdb": prediction,
                "native_pdb": native,
                "no_leak_evidence_ref": str(evidence),
                "leakage_clearance": "no_leak",
                "operator_clearance": "cleared",
                "operator": "operator-a",
                "prediction_created_at": "2026-01-01",
                "native_release_date": "2026-02-01",
                "prediction_generated_before_native_release": "true",
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "current_casp17_target": "false",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.8",
                "best_native_metric": "0.9",
                "selected_score": "10.0",
                "best_score": "11.0",
                "ablation_manifest_ref": str(ablation),
                "notes": "not complete",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, seed_inventory))

    payload = mod.build_payload(args)

    assert payload["summary"]["seed_clearance_status"] == "awaiting_seed_clearance"
    assert "no_leak_evidence_is_request_template" in payload["rows"][0]["blockers"]
