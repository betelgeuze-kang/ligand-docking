from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MODEL 1\nATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C  \nEND\n", encoding="utf-8")


def _write_preflight(path: Path, prediction: Path, native: Path, layer_dir: Path) -> None:
    ready_prediction = path.parent / "ready_predictions" / "T9001_prediction.pdb"
    ready_native = path.parent / "ready_natives" / "T9001_native.pdb"
    _write_pdb(ready_prediction)
    _write_pdb(ready_native)
    rows = [
        {
            "row_source": "scaffold",
            "benchmark_id": "hist_REQUIRED_MONOMER",
            "target_id": "REQUIRED_MONOMER",
            "scope": "monomer",
            "prediction_pdb": str(prediction),
            "native_pdb": str(native),
            "historical_ready": False,
            "ablation_ready": False,
            "missing_ablation_layers": "recursive,scored",
            "blockers": "placeholder_target_id,prediction_pdb_not_found,native_pdb_not_found,leakage_clearance_required,operator_clearance_required",
            "layer_prediction_paths_json": json.dumps(
                {
                    "recursive": str(layer_dir / "recursive" / "REQUIRED_MONOMERTS.pdb"),
                    "scored": str(layer_dir / "scored" / "REQUIRED_MONOMERTS.pdb"),
                }
            ),
        },
        {
            "row_source": "active_manifest",
            "benchmark_id": "hist_T9001",
            "target_id": "T9001",
            "scope": "monomer",
            "prediction_pdb": str(ready_prediction),
            "native_pdb": str(ready_native),
            "historical_ready": True,
            "ablation_ready": False,
            "missing_ablation_layers": "recursive",
            "blockers": "",
            "layer_prediction_paths_json": json.dumps({"recursive": str(layer_dir / "recursive" / "T9001TS.pdb")}),
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "preflight_status": "blocked",
                    "source_mode": "scaffold",
                    "source_artifact": "runs/casp17_historical_benchmark_manifest_scaffold_current.csv",
                },
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def test_historical_input_workorder_builds_operator_template(tmp_path: Path) -> None:
    preflight = tmp_path / "preflight.json"
    prediction = tmp_path / "predictions" / "REQUIRED_MONOMER_prediction.pdb"
    native = tmp_path / "natives" / "REQUIRED_MONOMER_native.pdb"
    _write_preflight(preflight, prediction, native, tmp_path / "layers")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_input_workorder_packet.py"),
            "--preflight-json",
            str(preflight),
            "--out-json",
            str(tmp_path / "workorder.json"),
            "--out-csv",
            str(tmp_path / "workorder.csv"),
            "--out-md",
            str(tmp_path / "workorder.md"),
            "--out-template-csv",
            str(tmp_path / "operator_template.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "workorder.json").read_text(encoding="utf-8"))
    template_rows = list(csv.DictReader((tmp_path / "operator_template.csv").open("r", encoding="utf-8", newline="")))
    md_text = (tmp_path / "workorder.md").read_text(encoding="utf-8")

    assert payload["summary"]["workorder_status"] == "ready"
    assert payload["summary"]["workorder_count"] == 2
    assert payload["summary"]["core_input_workorder_count"] == 1
    assert payload["summary"]["ablation_input_workorder_count"] == 1
    assert payload["summary"]["missing_core_file_count"] == 2
    assert payload["summary"]["missing_ablation_layer_count"] == 3
    assert payload["rows"][0]["workorder_status"] == "core_inputs_needed"
    assert "replace placeholder" in payload["rows"][0]["required_actions"]
    assert payload["rows"][1]["workorder_status"] == "ablation_inputs_needed"
    assert template_rows[0]["leakage_clearance"] == "REQUIRED_NO_LEAK_CLEARANCE"
    assert template_rows[0]["operator_clearance"] == "REQUIRED_OPERATOR_CLEARANCE"
    assert template_rows[0]["recursive_prediction_pdb"].endswith("REQUIRED_MONOMERTS.pdb")
    assert "does not fetch native structures" in payload["summary"]["claim_boundary"]
    assert "Operator Sequence" in md_text


def test_historical_input_workorder_blocks_when_preflight_missing(tmp_path: Path) -> None:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_historical_input_workorder_packet.py"),
            "--preflight-json",
            str(tmp_path / "missing.json"),
            "--out-json",
            str(tmp_path / "workorder.json"),
            "--out-csv",
            str(tmp_path / "workorder.csv"),
            "--out-md",
            str(tmp_path / "workorder.md"),
            "--out-template-csv",
            str(tmp_path / "operator_template.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "workorder.json").read_text(encoding="utf-8"))
    template_rows = list(csv.DictReader((tmp_path / "operator_template.csv").open("r", encoding="utf-8", newline="")))

    assert payload["summary"]["workorder_status"] == "blocked"
    assert payload["summary"]["workorder_count"] == 0
    assert template_rows == []
