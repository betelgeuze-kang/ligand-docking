from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_capri_round65_format_preflight_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _readiness_payload() -> dict:
    return {
        "rows": [
            {
                "capri_target_id": "T327",
                "casp_target_id": "H1311",
                "recommended_role": "closed",
            },
            {
                "capri_target_id": "T330",
                "casp_target_id": "T2313",
                "recommended_role": "scorer",
            },
        ],
        "summary": {"capri_readiness_status": "blocked_registration_role_selection"},
    }


def _valid_capri_pdb(target: str, model_count: int = 2) -> str:
    lines = [
        f"HEADER    CAPRI_{target}",
        "COMPND    MOL_ID: 1;",
        "COMPND   2 MOLECULE: TEST PROTEIN;",
        "COMPND   3 CHAIN: A;",
        "AUTHOR    local_preflight_fixture",
    ]
    atom_serial = 1
    for model in range(1, model_count + 1):
        lines.extend(
            [
                f"MODEL        {model}",
                "PARENT N/A",
                f"ATOM  {atom_serial:5d}  CA  ALA A   1       {model:6.3f}   0.000   0.000  1.00 80.00           C  ",
                f"TER   {atom_serial + 1:5d}      ALA A   1",
                "ENDMDL",
            ]
        )
        atom_serial += 2
    lines.append("END")
    return "\n".join(lines) + "\n"


def test_format_preflight_blocks_missing_candidate_and_template(tmp_path: Path) -> None:
    readiness_json = tmp_path / "readiness.json"
    _write_json(readiness_json, _readiness_payload())
    args = mod.parse_args(
        [
            "--readiness-json",
            str(readiness_json),
            "--dropzone-dir",
            str(tmp_path / "dropzones"),
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "preflight.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["format_preflight_status"] == "blocked_format_preflight"
    assert payload["summary"]["target_count"] == 2
    assert payload["summary"]["active_target_count"] == 1
    assert payload["summary"]["closed_target_count"] == 1
    assert payload["summary"]["blocked_target_count"] == 1
    assert payload["summary"]["target_template_missing_count"] == 1
    assert payload["summary"]["candidate_submission_missing_count"] == 1
    assert payload["summary"]["first_blocked_target_id"] == "T330"
    assert payload["rows"][0]["preflight_status"] == "closed_context"
    assert payload["rows"][1]["role"] == "scorer"
    assert "candidate_submission_pdb_missing" in payload["rows"][1]["blockers"]
    assert (tmp_path / "dropzones" / "T330_T2313" / "ACTION.md").exists()
    assert (tmp_path / "dropzones" / "T330_T2313" / "format_checklist.csv").exists()


def test_format_preflight_passes_local_capri_pdb_shape(tmp_path: Path) -> None:
    readiness_json = tmp_path / "readiness.json"
    _write_json(readiness_json, {"rows": [_readiness_payload()["rows"][1]]})
    dropzone = tmp_path / "dropzones" / "T330_T2313"
    dropzone.mkdir(parents=True)
    (dropzone / "target_template.pdb").write_text(_valid_capri_pdb("T330", model_count=1), encoding="utf-8")
    (dropzone / "candidate_submission.pdb").write_text(_valid_capri_pdb("T330", model_count=2), encoding="utf-8")
    args = mod.parse_args(
        [
            "--readiness-json",
            str(readiness_json),
            "--dropzone-dir",
            str(tmp_path / "dropzones"),
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "preflight.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["format_preflight_status"] == "format_preflight_pass_local"
    assert payload["summary"]["local_pass_count"] == 1
    assert payload["summary"]["blocked_target_count"] == 0
    assert payload["summary"]["checked_submission_count"] == 1
    row = payload["rows"][0]
    assert row["model_count"] == 2
    assert row["model_limit"] == 10
    assert row["atom_record_count"] == 2
    assert row["header_ok"] is True
    assert row["model_order_ok"] is True
    assert row["ter_ok"] is True
    assert row["end_ok"] is True
    assert row["blockers"] == ""
