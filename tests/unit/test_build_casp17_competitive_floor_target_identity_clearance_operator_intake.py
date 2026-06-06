import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_operator_intake as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _pdb(path: Path, *, residue: str = "ALA", x: str = "1.000", y: str = "2.000", z: str = "3.000") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"ATOM      1  CA  {residue} A   1       {x}   {y}   {z}  1.00 70.00           C\n")
    return str(path)


def _workorder(tmp_path: Path) -> dict[str, Path]:
    target_id = "H1001"
    prediction = _pdb(tmp_path / "prediction" / f"{target_id}_model_1.pdb")
    native_dropzone = tmp_path / "workorder" / "native" / f"{target_id}_native.pdb"
    provenance = tmp_path / "workorder" / "provenance_template.csv"
    manifest = tmp_path / "workorder" / "manifest_stub.csv"
    _write_csv(
        provenance,
        [
            {
                "benchmark_id": f"hist_{target_id}_clearance_candidate",
                "target_id": target_id,
                "scope": "complex",
                "split": "historical_candidate",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "prediction_method": "internal_prediction_from_clearance_queue",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "evidence_ref": "REQUIRED_NO_LEAK_EVIDENCE_REF",
                "notes": "pending",
            }
        ],
    )
    _write_csv(manifest, [{"target_id": target_id, "prediction_pdb": prediction, "native_pdb": str(native_dropzone)}])
    workorder_json = tmp_path / "workorder.json"
    _write_json(
        workorder_json,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [
                {
                    "target_id": target_id,
                    "scope": "complex",
                    "workorder_status": "native_and_provenance_required",
                    "native_dropzone_pdb": str(native_dropzone),
                    "provenance_template_csv": str(provenance),
                    "manifest_stub_csv": str(manifest),
                    "prediction_pdb": prediction,
                }
            ],
        },
    )
    return {"workorder_json": workorder_json, "native_dropzone": native_dropzone, "provenance": provenance}


def _args(tmp_path: Path, fixture: dict[str, Path], *extra: str) -> list[str]:
    return [
        "--workorder-json",
        str(fixture["workorder_json"]),
        "--intake-csv",
        str(tmp_path / "operator_intake.csv"),
        "--out-json",
        str(tmp_path / "operator_intake.json"),
        "--out-csv",
        str(tmp_path / "operator_intake_report.csv"),
        "--out-md",
        str(tmp_path / "OPERATOR_INTAKE.md"),
        *extra,
    ]


def test_operator_intake_creates_template_and_waits_for_input(tmp_path: Path) -> None:
    fixture = _workorder(tmp_path)
    args = mod.parse_args(_args(tmp_path, fixture))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["operator_intake_status"] == "awaiting_input"
    assert payload["summary"]["template_status"] == "created"
    assert payload["summary"]["awaiting_input_count"] == 1
    assert payload["rows"][0]["native_action_status"] == "waiting_on_input"
    assert (tmp_path / "operator_intake.csv").is_file()
    assert (tmp_path / "OPERATOR_INTAKE.md").is_file()


def test_operator_intake_apply_copies_native_and_patches_provenance(tmp_path: Path) -> None:
    fixture = _workorder(tmp_path)
    native_source = _pdb(tmp_path / "sources" / "H1001_native.pdb", residue="GLY", x="4.000", y="5.000", z="6.000")
    evidence = tmp_path / "evidence" / "H1001_no_leak.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("H1001 completed no-leak operator review. no leak controls cleared.\n", encoding="utf-8")
    _write_csv(
        tmp_path / "operator_intake.csv",
        [
            {
                "target_id": "H1001",
                "native_source_pdb": native_source,
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
                "notes": "operator reviewed no-leak evidence",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, fixture, "--apply"))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["operator_intake_status"] == "applied"
    assert payload["summary"]["native_copied_count"] == 1
    assert payload["summary"]["provenance_patched_count"] == 1
    assert fixture["native_dropzone"].is_file()
    provenance = _read_csv(fixture["provenance"])[0]
    assert provenance["leakage_clearance"] == "no_leak"
    assert provenance["operator_clearance"] == "cleared"
    assert provenance["evidence_ref"] == str(evidence)


def test_operator_intake_blocks_evidence_request_template(tmp_path: Path) -> None:
    fixture = _workorder(tmp_path)
    native_source = _pdb(tmp_path / "sources" / "H1001_native.pdb", residue="GLY")
    evidence = tmp_path / "evidence_request.md"
    evidence.write_text(
        "CLEARANCE_EVIDENCE_STATUS: request_template\nH1001 evidence request template. not a completed no-leak clearance.\n",
        encoding="utf-8",
    )
    _write_csv(
        tmp_path / "operator_intake.csv",
        [
            {
                "target_id": "H1001",
                "native_source_pdb": native_source,
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
                "notes": "operator reviewed no-leak evidence",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, fixture))

    payload = mod.build_payload(args)

    assert payload["summary"]["operator_intake_status"] == "blocked"
    assert "no_leak_evidence_is_request_template" in payload["rows"][0]["blockers"]
