from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_identity_seed_clearance_action_bundle as mod


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


def _pdb(path: Path, x: float) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"ATOM      1  CA  ALA A   1       {x:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00 20.00           C\n",
        encoding="utf-8",
    )
    return str(path)


def _args(tmp_path: Path, workorder_json: Path) -> list[str]:
    return [
        "--workorder-json",
        str(workorder_json),
        "--out-dir",
        str(tmp_path / "action_bundle"),
        "--out-json",
        str(tmp_path / "action_bundle.json"),
        "--out-csv",
        str(tmp_path / "action_bundle.csv"),
        "--out-md",
        str(tmp_path / "ACTION_BUNDLE.md"),
    ]


def test_seed_clearance_action_bundle_materializes_open_phase_requests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    prediction = _pdb(tmp_path / "prediction.pdb", 1.0)
    native = _pdb(tmp_path / "native.pdb", 4.0)
    operator_csv = tmp_path / "operator.csv"
    _write_csv(
        operator_csv,
        [
            {
                "target_id": "HIST_BBA5",
                "prediction_pdb": prediction,
                "native_pdb": native,
            }
        ],
    )
    workorder_json = tmp_path / "workorder.json"
    _write_json(
        workorder_json,
        {
            "summary": {"operator_clearance_csv": str(operator_csv)},
            "rows": [
                {
                    "seed_rank": 1,
                    "batch_slot": 1,
                    "target_id": "HIST_BBA5",
                    "scope": "monomer",
                    "clearance_status": "awaiting_seed_clearance",
                    "identity_status": "ready",
                    "core_files_status": "ready",
                    "no_leak_provenance_status": "awaiting_no_leak_provenance",
                    "calibration_status": "awaiting_calibration_values",
                    "ablation_status": "awaiting_ablation_manifest",
                    "blockers": "no_leak_evidence_ref_required,selected_score_required_numeric,ablation_manifest_ref_required",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, workorder_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["seed_clearance_action_bundle_status"] == "open_actions"
    assert summary["target_count"] == 1
    assert summary["action_count"] == 3
    assert summary["open_action_count"] == 3
    assert summary["target_folder_count"] == 1
    assert summary["action_folder_count"] == 3
    assert summary["bundle_file_count"] == 6
    assert summary["identity_action_count"] == 0
    assert summary["core_file_action_count"] == 0
    assert summary["no_leak_action_count"] == 1
    assert summary["calibration_action_count"] == 1
    assert summary["ablation_action_count"] == 1
    assert summary["first_open_action_md"].endswith("action_001_no_leak_provenance/ACTION.md")

    by_lane = {row["lane"]: row for row in payload["rows"]}
    request = Path(by_lane["no_leak_provenance"]["request_md"])
    if not request.is_absolute():
        request = mod.ROOT / request
    request_text = request.read_text(encoding="utf-8")
    assert "CLEARANCE_EVIDENCE_STATUS: request_template" in request_text
    assert "not completed no-leak evidence" in request_text
    assert "sha256_16=" in request_text
    assert (tmp_path / "action_bundle.csv").is_file()
    assert (tmp_path / "ACTION_BUNDLE.md").is_file()


def test_seed_clearance_action_bundle_missing_rows_is_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    workorder_json = tmp_path / "workorder.json"
    _write_json(workorder_json, {"summary": {"operator_clearance_csv": "operator.csv"}, "rows": []})
    args = mod.parse_args(_args(tmp_path, workorder_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["seed_clearance_action_bundle_status"] == "missing_workorder_rows"
    assert payload["summary"]["action_count"] == 0
    assert payload["summary"]["bundle_file_count"] == 0
    assert payload["rows"] == []
