import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_score_ledger as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pdb(coords: list[tuple[float, float, float]]) -> str:
    lines = ["MODEL        1"]
    for serial, (x, y, z) in enumerate(coords, start=1):
        lines.append(
            f"ATOM  {serial:5d}  CA  ALA A{serial:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 50.00           C"
        )
    lines.extend(["ENDMDL", "END"])
    return "\n".join(lines) + "\n"


def test_scores_first_baseline_model1_and_top5(tmp_path):
    native_coords = [
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 2.0, 0.0),
        (0.0, 0.0, 2.0),
        (2.0, 2.0, 2.0),
    ]
    distorted_coords = [
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 2.0, 0.0),
        (12.0, 12.0, 12.0),
        (14.0, 14.0, 14.0),
    ]
    native = tmp_path / "9XYZ.pdb"
    native.write_text(_pdb(native_coords), encoding="utf-8")
    rows = []
    for group_id in ("001", "002"):
        for model_number in range(1, 6):
            model_id = f"T9999TS{group_id}_{model_number}"
            model_path = tmp_path / "models" / f"{model_id}.pdb"
            coords = native_coords
            if group_id == "001" and model_number == 1:
                coords = distorted_coords
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model_path.write_text(_pdb(coords), encoding="utf-8")
            rows.append(
                {
                    "target_id": "T9999",
                    "group_id": group_id,
                    "model_id": model_id,
                    "model_number": model_number,
                    "pool_role": "model1" if model_number == 1 else "top5",
                    "extracted_pdb": str(model_path),
                    "model_status": "model_ready",
                }
            )
    model_pool_json = tmp_path / "model_pool.json"
    _write_json(
        model_pool_json,
        {
            "summary": {
                "official_archive_first_baseline_model_pool_status": (
                    "official_archive_first_baseline_model_pool_ready"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T9999",
                "first_native_pdb_code": "9XYZ",
                "native_pdb_path": str(native),
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            },
            "rows": rows,
        },
    )
    args = mod.parse_args(
        [
            "--model-pool-json",
            str(model_pool_json),
            "--out-dir",
            str(tmp_path / "score"),
            "--out-json",
            str(tmp_path / "score.json"),
            "--out-csv",
            str(tmp_path / "score.csv"),
            "--out-md",
            str(tmp_path / "SCORE.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_first_baseline_score_ledger_status"] == (
        "official_archive_first_baseline_score_ledger_ready_baseline_only"
    )
    assert summary["first_target_id"] == "T9999"
    assert summary["top5_model_count"] == 10
    assert summary["scored_model_count"] == 10
    assert summary["blocked_model_count"] == 0
    assert summary["group_count"] == 2
    assert summary["ready_group_count"] == 2
    assert summary["complete_top5_group_count"] == 2
    assert summary["model1_group_count"] == 2
    assert summary["best_top5_group_count"] == 2
    assert summary["top5_improved_group_count"] == 1
    assert summary["competitive_proof_eligible"] is False
    assert summary["strict_blind_intake_policy"] == "do_not_import_as_internal_prediction"
    assert payload["model_score_rows"][0]["metric_status"] == "metric_ready"
    assert (tmp_path / "score" / "model_score_rows.csv").exists()
    assert (tmp_path / "score" / "group_score_ledger.csv").exists()
    assert "Claim Boundary" in (tmp_path / "SCORE.md").read_text(encoding="utf-8")
