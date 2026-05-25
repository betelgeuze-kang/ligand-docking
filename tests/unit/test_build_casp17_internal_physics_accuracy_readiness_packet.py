from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _atom(serial: int, chain_id: str, resseq: int) -> str:
    return (
        f"ATOM  {serial:5d} CA   ALA {chain_id}{resseq:4d}    "
        f"{float(serial):8.3f}{0.0:8.3f}{0.0:8.3f}{1.00:6.2f}{50.0 + serial:6.2f}           C  "
    )


def _write_fixture(tmp_path: Path, *, contacts: int = 6) -> dict[str, Path]:
    target_id = "H9999"
    prediction = tmp_path / "predictions/H9999TS.pdb"
    prediction.parent.mkdir(parents=True)
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET H9999",
                "AUTHOR 1234-5678-ABCD",
                "METHOD internal test",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "A", 1),
                _atom(2, "A", 2),
                _atom(3, "A", 3),
                _atom(4, "A", 4),
                "TER",
                "PARENT N/A",
                _atom(5, "B", 1),
                _atom(6, "B", 2),
                _atom(7, "B", 3),
                _atom(8, "B", 4),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    job_dir = tmp_path / "jobs/H9999"
    _write_json(
        job_dir / "internal_physics_metrics.json",
        {
            "summary": {
                "target_id": target_id,
                "chain_count": 2,
                "residue_count": 2,
                "ensemble_size": 32,
                "steps": 2500,
            },
            "chains": [
                {
                    "chain_id": "A",
                    "sequence_length": 1,
                    "energy": 1.0,
                    "rg_A": 8.0,
                    "ca_distance_min_A": 3.8,
                    "ca_distance_max_A": 3.8,
                    "confidence_mean": 70.0,
                },
                {
                    "chain_id": "B",
                    "sequence_length": 1,
                    "energy": 1.0,
                    "rg_A": 8.0,
                    "ca_distance_min_A": 3.8,
                    "ca_distance_max_A": 3.8,
                    "confidence_mean": 69.0,
                },
            ],
            "assembly": {
                "chain_count": 2,
                "chain_pair_count": 1,
                "interchain_ca_contact_count_12A": contacts,
                "chain_pairs_with_contacts_12A": 1 if contacts else 0,
                "min_interchain_ca_distance_A": 4.0,
                "interchain_ca_clash_count_3A": 0,
            },
        },
    )
    paths = {
        "watchlist": tmp_path / "watchlist.json",
        "raw_gate": tmp_path / "raw_gate.json",
        "ts_gate": tmp_path / "ts_gate.json",
        "submission_gate": tmp_path / "submission_gate.json",
        "job_root": tmp_path / "jobs",
        "prediction": prediction,
    }
    _write_json(
        paths["watchlist"],
        {"rows": [{"target_id": target_id, "human_open": True, "lane_recommendation": "difficult_protein_complexes"}]},
    )
    _write_json(paths["raw_gate"], {"rows": [{"target_id": target_id, "raw_gate_status": "pass"}]})
    _write_json(paths["ts_gate"], {"rows": [{"target_id": target_id, "ts_conversion_status": "converted", "ts_pdb": str(prediction)}]})
    _write_json(
        paths["submission_gate"],
        {
            "target_rows": [
                {
                    "target_id": target_id,
                    "submission_decision": "submission_go",
                    "prediction_file_path": str(prediction),
                }
            ]
        },
    )
    return paths


def _run_tool(tmp_path: Path, paths: dict[str, Path], *, require_backbone_atoms: bool = False) -> tuple[int, dict]:
    out_json = tmp_path / "readiness.json"
    command = [
        "python3",
        str(ROOT / "tools/build_casp17_internal_physics_accuracy_readiness_packet.py"),
        "--target-watchlist-json",
        str(paths["watchlist"]),
        "--raw-gate-json",
        str(paths["raw_gate"]),
        "--ts-gate-json",
        str(paths["ts_gate"]),
        "--submission-gate-json",
        str(paths["submission_gate"]),
        "--job-dir",
        str(paths["job_root"]),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(tmp_path / "readiness.csv"),
        "--out-md",
        str(tmp_path / "readiness.md"),
    ]
    if require_backbone_atoms:
        command.append("--require-backbone-atoms")
    run = subprocess.run(command, cwd=ROOT, check=False)
    return run.returncode, json.loads(out_json.read_text(encoding="utf-8"))


def test_internal_physics_accuracy_readiness_passes_proxy_fixture(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, contacts=6)

    returncode, payload = _run_tool(tmp_path, paths, require_backbone_atoms=True)

    assert returncode == 0
    assert payload["summary"]["accuracy_readiness_status"] == "pass"
    assert payload["rows"][0]["accuracy_readiness_status"] == "pass"


def test_internal_physics_accuracy_readiness_fails_missing_interface_contacts(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, contacts=0)

    returncode, payload = _run_tool(tmp_path, paths)

    assert returncode == 2
    assert payload["summary"]["accuracy_readiness_status"] == "fail"
    assert "interchain_contact_count_below_proxy_floor" in payload["rows"][0]["blockers"]


def test_internal_physics_accuracy_readiness_fails_current_open_target_missing_from_submission_gate(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, contacts=6)
    _write_json(
        paths["watchlist"],
        {
            "rows": [
                {"target_id": "H9999", "human_open": True, "lane_recommendation": "difficult_protein_complexes"},
                {"target_id": "T9998", "human_open": True, "lane_recommendation": "difficult_protein_complexes"},
            ]
        },
    )

    returncode, payload = _run_tool(tmp_path, paths)
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert returncode == 2
    assert payload["summary"]["target_count"] == 2
    assert rows["T9998"]["accuracy_readiness_status"] == "fail"
    assert "submission_gate_not_go" in rows["T9998"]["blockers"]
