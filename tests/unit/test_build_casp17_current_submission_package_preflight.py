import json
from pathlib import Path

from tools import build_casp17_current_submission_package_preflight as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_fasta(path: Path, target_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f">{target_id}\nAA\n", encoding="utf-8")


def _atom(serial: int, residue: int, b_factor: float) -> str:
    return (
        f"ATOM  {serial:5d}  CA  ALA A{residue:4d}    "
        f"{float(residue):8.3f}{0.0:8.3f}{0.0:8.3f}"
        f"{1.0:6.2f}{b_factor:6.2f}           C"
    )


def _write_ts(path: Path, target_id: str, author: str = "A123") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                f"TARGET {target_id}",
                f"AUTHOR {author}",
                "METHOD manifest-only preflight fixture",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, 1, 55.0),
                _atom(2, 2, 65.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _base_inputs(tmp_path: Path, *, author: str = "A123") -> dict[str, Path]:
    target_id = "T9001"
    fasta = tmp_path / "targets" / target_id / f"{target_id}.fasta"
    prediction_dir = tmp_path / "predictions"
    prediction = prediction_dir / f"{target_id}TS.pdb"
    target_json = tmp_path / "target_model_folders.json"
    gate_json = tmp_path / "submission_gate.json"
    sidechain_json = tmp_path / "sidechain_repack.json"

    _write_fasta(fasta, target_id)
    _write_ts(prediction, target_id, author=author)
    _write_json(
        target_json,
        {
            "summary": {"target_count": 1, "ready_count": 1},
            "rows": [
                {
                    "target_id": target_id,
                    "protein_name": "Fixture protein",
                    "lane": "difficult_protein_complexes",
                    "folder_status": "ready",
                    "folder_path": "casp17/targets_current/T9001_Fixture",
                    "fasta_path": str(fasta),
                }
            ],
        },
    )
    _write_json(
        gate_json,
        {
            "summary": {
                "submission_go_count": 1,
                "submission_no_go_count": 0,
                "target_row_count": 1,
                "framework_gate_pass": True,
                "server_registration_ready": False,
            }
        },
    )
    _write_json(
        sidechain_json,
        {
            "summary": {"sidechain_repack_status": "pass", "pass_count": 1, "blocked_count": 0},
            "rows": [{"target_id": target_id, "sidechain_repack_status": "pass"}],
        },
    )
    return {
        "target_json": target_json,
        "gate_json": gate_json,
        "sidechain_json": sidechain_json,
        "prediction_dir": prediction_dir,
    }


def test_current_submission_package_preflight_ready_and_redacts_author(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path, author="A123")
    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(paths["target_json"]),
            "--submission-gate-json",
            str(paths["gate_json"]),
            "--sidechain-repack-json",
            str(paths["sidechain_json"]),
            "--prediction-dir",
            str(paths["prediction_dir"]),
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "preflight.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["package_preflight_status"] == "ready"
    assert summary["ready_count"] == 1
    assert summary["blocked_count"] == 0
    assert summary["candidate_file_present_count"] == 1
    assert summary["candidate_sha256_count"] == 1
    assert summary["format_pass_count"] == 1
    assert summary["author_record_pass_count"] == 1
    assert summary["sidechain_repack_pass_count"] == 1
    assert summary["runtime_author_code_policy"] == "author_code_checked_from_existing_TS_headers_redacted_not_serialized"
    assert row["package_preflight_status"] == "ready"
    assert row["format_check_status"] == "pass"
    assert row["author_record_status"] == "author_present_redacted"
    assert row["candidate_sha256"]
    assert "A123" not in json.dumps(payload)
    assert "A123" not in Path(args.out_md).read_text(encoding="utf-8")


def test_current_submission_package_preflight_blocks_placeholder_author(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path, author="TEST")
    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(paths["target_json"]),
            "--submission-gate-json",
            str(paths["gate_json"]),
            "--sidechain-repack-json",
            str(paths["sidechain_json"]),
            "--prediction-dir",
            str(paths["prediction_dir"]),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["package_preflight_status"] == "blocked"
    assert payload["summary"]["ready_count"] == 0
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["author_record_pass_count"] == 0
    assert payload["rows"][0]["author_record_status"] == "author_placeholder_blocked"
    assert "author_placeholder_blocked" in payload["rows"][0]["blockers"]
    assert "TEST" not in json.dumps(payload)
