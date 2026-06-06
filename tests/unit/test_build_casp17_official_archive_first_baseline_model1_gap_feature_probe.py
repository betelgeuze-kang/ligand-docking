import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_model1_gap_feature_probe as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _pdb_line(serial: int, chain: str, residue: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d}  CA  ALA {chain}{residue:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C\n"
    )


def _write_ca_pdb(path: Path, points: list[tuple[float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_pdb_line(index, "A", index, *point) for index, point in enumerate(points, start=1)]
    path.write_text("".join(lines) + "END\n", encoding="utf-8")


def test_build_feature_probe_scores_native_free_model1_risk(tmp_path):
    broken_model1 = tmp_path / "broken_model1.pdb"
    compact_best = tmp_path / "compact_best.pdb"
    similar_model1 = tmp_path / "similar_model1.pdb"
    similar_best = tmp_path / "similar_best.pdb"
    _write_ca_pdb(broken_model1, [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (24.0, 0.0, 0.0)])
    _write_ca_pdb(compact_best, [(0.0, 0.0, 0.0), (3.8, 0.0, 0.0), (7.6, 0.0, 0.0)])
    _write_ca_pdb(similar_model1, [(0.0, 0.0, 0.0), (3.8, 0.0, 0.0), (7.6, 0.0, 0.0)])
    _write_ca_pdb(similar_best, [(0.0, 0.1, 0.0), (3.8, 0.1, 0.0), (7.6, 0.1, 0.0)])
    viewer_json = tmp_path / "viewer_packet.json"
    _write_json(
        viewer_json,
        {
            "summary": {
                "official_archive_first_baseline_model1_gap_viewer_packet_status": (
                    "official_archive_first_baseline_model1_gap_viewer_packet_ready_baseline_only"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T1212",
                "first_native_pdb_code": "9B0L",
            },
            "rows": [
                {
                    "target_id": "T1212",
                    "group_id": "163",
                    "triage_band": "catastrophic_model1_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "78.380",
                    "model1_model_id": "T1212TS163_1",
                    "best_top5_model_id": "T1212TS163_4",
                    "model1_pdb": str(broken_model1),
                    "best_top5_pdb": str(compact_best),
                },
                {
                    "target_id": "T1212",
                    "group_id": "304",
                    "triage_band": "large_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "12.000",
                    "model1_model_id": "T1212TS304_1",
                    "best_top5_model_id": "T1212TS304_3",
                    "model1_pdb": str(similar_model1),
                    "best_top5_pdb": str(similar_best),
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--viewer-packet-json",
            str(viewer_json),
            "--out-dir",
            str(tmp_path / "features"),
            "--out-json",
            str(tmp_path / "features.json"),
            "--out-csv",
            str(tmp_path / "features.csv"),
            "--out-md",
            str(tmp_path / "FEATURES.md"),
        ]
    )

    payload = mod.build_payload(args)
    summary = payload["summary"]

    assert summary["official_archive_first_baseline_model1_gap_feature_probe_status"] == (
        "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
    )
    assert summary["selected_case_count"] == 2
    assert summary["feature_ready_count"] == 2
    assert summary["supports_best_top5_count"] == 1
    assert summary["ambiguous_count"] == 1
    assert payload["rows"][0]["geometry_signal"] == "supports_best_top5"
    assert float(payload["rows"][0]["model1_geometry_risk_score"]) > float(
        payload["rows"][0]["best_top5_geometry_risk_score"]
    )
    assert len(payload["pair_feature_matrix"]) == 4

    mod.write_outputs(args, payload)

    assert (tmp_path / "features.json").is_file()
    assert (tmp_path / "features.csv").is_file()
    assert (tmp_path / "FEATURES.md").is_file()
    assert (tmp_path / "features" / "pair_feature_matrix.csv").is_file()
