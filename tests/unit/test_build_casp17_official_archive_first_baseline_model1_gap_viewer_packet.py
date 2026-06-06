import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_model1_gap_viewer_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pdb(offset: float) -> str:
    lines = []
    for idx in range(1, 5):
        lines.append(
            f"ATOM  {idx:5d}  CA  ALA A{idx:4d}    "
            f"{idx + offset:8.3f}{idx * 2 + offset:8.3f}{idx * 3 + offset:8.3f}  1.00 50.00           C"
        )
    lines.append("END")
    return "\n".join(lines) + "\n"


def test_builds_model1_gap_viewer_packet(tmp_path):
    model1 = tmp_path / "models" / "T9999TS001_1.pdb"
    best = tmp_path / "models" / "T9999TS001_4.pdb"
    native = tmp_path / "native" / "9XYZ.pdb"
    model1.parent.mkdir(parents=True, exist_ok=True)
    native.parent.mkdir(parents=True, exist_ok=True)
    model1.write_text(_pdb(0.0), encoding="utf-8")
    best.write_text(_pdb(3.0), encoding="utf-8")
    native.write_text(_pdb(1.0), encoding="utf-8")
    triage_json = tmp_path / "triage.json"
    score_json = tmp_path / "score.json"
    _write_json(
        triage_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_triage_status": (
                    "official_archive_first_baseline_model1_gap_triage_ready_baseline_only"
                )
            },
            "rows": [
                {
                    "target_id": "T9999",
                    "group_id": "001",
                    "triage_band": "catastrophic_model1_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "70.000",
                    "model1_model_id": "T9999TS001_1",
                    "model1_gdt_ts_proxy": "10.000",
                    "best_top5_model_id": "T9999TS001_4",
                    "best_top5_gdt_ts_proxy": "80.000",
                }
            ],
        },
    )
    _write_json(
        score_json,
        {
            "summary": {
                "official_archive_first_baseline_score_ledger_status": (
                    "official_archive_first_baseline_score_ledger_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T9999",
                "first_native_pdb_code": "9XYZ",
                "native_pdb": str(native),
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
            },
            "model_score_rows": [
                {"model_id": "T9999TS001_1", "path": str(model1)},
                {"model_id": "T9999TS001_4", "path": str(best)},
            ],
        },
    )
    args = mod.parse_args(
        [
            "--triage-json",
            str(triage_json),
            "--score-ledger-json",
            str(score_json),
            "--out-dir",
            str(tmp_path / "viewers"),
            "--out-json",
            str(tmp_path / "viewers.json"),
            "--out-csv",
            str(tmp_path / "viewers.csv"),
            "--out-md",
            str(tmp_path / "VIEWERS.md"),
            "--max-cases",
            "1",
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["official_archive_first_baseline_model1_gap_viewer_packet_status"] == (
        "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
    )
    assert summary["selected_case_count"] == 1
    assert summary["viewer_ready_count"] == 1
    assert summary["native_reference_ready"] is True
    assert summary["first_viewer_group_id"] == "001"
    assert row["viewer_status"] == "viewer_ready"
    assert Path(row["viewer_html"]).is_file() or (tmp_path / "viewers.json").exists()
    assert (tmp_path / "viewers" / "gallery.html").exists()
    assert "Claim Boundary" in (tmp_path / "VIEWERS.md").read_text(encoding="utf-8")
