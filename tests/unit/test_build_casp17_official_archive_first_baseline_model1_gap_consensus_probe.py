import json
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_model1_gap_consensus_probe as mod


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
    path.write_text(
        "".join(_pdb_line(index, "A", index, *point) for index, point in enumerate(points, start=1))
        + "END\n",
        encoding="utf-8",
    )


def test_consensus_probe_marks_model1_outlier_against_top5_cluster(tmp_path):
    compact = [(0.0, 0.0, 0.0), (3.8, 0.0, 0.0), (7.6, 0.0, 0.0), (11.4, 0.0, 0.0), (15.2, 0.0, 0.0)]
    compact_shift = [(x, y + 0.1, z) for x, y, z in compact]
    compact_soft = [(x, y, z + 0.2) for x, y, z in compact]
    compact_tilt = [(x, y + index * 0.04, z) for index, (x, y, z) in enumerate(compact)]
    outlier = [(0.0, 0.0, 0.0), (3.8, 5.0, 0.0), (7.6, -5.0, 0.0), (11.4, 5.0, 0.0), (15.2, -5.0, 0.0)]
    paths = {
        "T000TS101_1": tmp_path / "T000TS101_1.pdb",
        "T000TS101_2": tmp_path / "T000TS101_2.pdb",
        "T000TS101_3": tmp_path / "T000TS101_3.pdb",
        "T000TS101_4": tmp_path / "T000TS101_4.pdb",
        "T000TS101_5": tmp_path / "T000TS101_5.pdb",
    }
    _write_ca_pdb(paths["T000TS101_1"], outlier)
    _write_ca_pdb(paths["T000TS101_2"], compact)
    _write_ca_pdb(paths["T000TS101_3"], compact_shift)
    _write_ca_pdb(paths["T000TS101_4"], compact_soft)
    _write_ca_pdb(paths["T000TS101_5"], compact_tilt)
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
                    "target_id": "T000",
                    "group_id": "101",
                    "triage_band": "catastrophic_model1_selection_gap",
                    "best_minus_model1_gdt_ts_proxy": "55.000",
                    "model1_model_id": "T000TS101_1",
                    "best_top5_model_id": "T000TS101_2",
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
                "first_target_id": "T000",
                "first_native_pdb_code": "TEST",
            },
            "model_score_rows": [
                {
                    "target_id": "T000",
                    "group_id": "101",
                    "model_id": model_id,
                    "model_number": index,
                    "path": str(paths[model_id]),
                    "metric_status": "metric_ready",
                    "gdt_ts_proxy": str(100 - index),
                }
                for index, model_id in enumerate(paths, start=1)
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
            str(tmp_path / "consensus"),
            "--out-json",
            str(tmp_path / "consensus.json"),
            "--out-csv",
            str(tmp_path / "consensus.csv"),
            "--out-md",
            str(tmp_path / "CONSENSUS.md"),
            "--signal-threshold",
            "0.5",
        ]
    )

    payload = mod.build_payload(args)
    row = payload["rows"][0]

    assert payload["summary"]["official_archive_first_baseline_model1_gap_consensus_probe_status"] == (
        "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
    )
    assert row["consensus_signal"] == "supports_best_top5"
    assert int(row["best_top5_consensus_rank"]) < int(row["model1_consensus_rank"])
    assert float(row["consensus_margin_model1_minus_best"]) > 0.5
    assert len(payload["pairwise_consensus_matrix"]) == 10

    mod.write_outputs(args, payload)

    assert (tmp_path / "consensus.json").is_file()
    assert (tmp_path / "consensus.csv").is_file()
    assert (tmp_path / "CONSENSUS.md").is_file()
    assert (tmp_path / "consensus" / "pairwise_consensus_matrix.csv").is_file()
