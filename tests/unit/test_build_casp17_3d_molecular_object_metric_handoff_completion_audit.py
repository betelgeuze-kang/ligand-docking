import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_3d_molecular_object_metric_handoff_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_metric_csv(path: Path, metrics: list[str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "metric_name",
                "metric_family",
                "metric_input_contract",
                "metric_evidence_status",
                "expected_output_status",
                "competitive_proof_eligible",
                "claim_boundary",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for metric in metrics:
            writer.writerow(
                {
                    "metric_name": metric,
                    "metric_family": "protein_complex",
                    "metric_input_contract": "prediction/native mapping",
                    "metric_evidence_status": mod.METRIC_EVIDENCE_STATUS,
                    "expected_output_status": "not_computed_review_only",
                    "competitive_proof_eligible": "false",
                    "claim_boundary": "review only",
                }
            )
    return str(path)


def _handoff_row(
    tmp_path: Path,
    protein_key: str,
    object_key: str,
    metrics: list[str],
    lane: str = "current_object_library",
) -> dict:
    handoff_protein = tmp_path / "handoff" / protein_key
    handoff_object = handoff_protein / object_key
    atlas_object = tmp_path / "atlas" / protein_key / object_key
    _touch(handoff_protein / "README.md")
    _write_json(handoff_protein / "protein_metric_handoff_manifest.json", {"summary": {"protein": protein_key}})
    _write_json(handoff_object / "metric_handoff_manifest.json", {"summary": {"object": object_key}})
    _touch(handoff_object / "METRIC_HANDOFF.md")
    _write_metric_csv(handoff_object / "metric_requirements.csv", metrics)
    _write_json(atlas_object / "object_manifest.json", {"summary": {"object": object_key}})
    row = {
        "atlas_protein_key": protein_key,
        "atlas_object_key": object_key,
        "source_lane": lane,
        "target_id": protein_key.split("_", 1)[0],
        "protein_name": protein_key.split("_", 1)[1],
        "object_id": object_key,
        "metric_family": "protein_complex",
        "handoff_status": "ready_review_only",
        "metric_evidence_status": mod.METRIC_EVIDENCE_STATUS,
        "metric_requirement_count": len(metrics),
        "required_metric_names": "|".join(metrics),
        "handoff_protein_folder": str(handoff_protein),
        "handoff_protein_manifest": str(handoff_protein / "protein_metric_handoff_manifest.json"),
        "handoff_object_folder": str(handoff_object),
        "handoff_object_manifest": str(handoff_object / "metric_handoff_manifest.json"),
        "metric_requirements_csv": str(handoff_object / "metric_requirements.csv"),
        "metric_handoff_md": str(handoff_object / "METRIC_HANDOFF.md"),
        "atlas_object_folder": str(atlas_object),
        "atlas_object_manifest": str(atlas_object / "object_manifest.json"),
        "model_path": _touch(tmp_path / "models" / f"{object_key}.pdb", "ATOM\n"),
        "viewer_html": _touch(tmp_path / "viewers" / f"{object_key}.html"),
        "projection_svg": _touch(tmp_path / "renders" / f"{object_key}.svg"),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }
    if lane == "massivefold_freeze_candidate":
        row.update(
            {
                "model_sha256": "model-sha",
                "top5_manifest_csv": _touch(tmp_path / "top5" / f"{object_key}.csv"),
                "top5_manifest_sha256": "top5-sha",
                "escrow_md": _touch(tmp_path / "escrow" / f"{object_key}.md"),
            }
        )
    return row


def test_metric_handoff_completion_audit_passes_complete_handoff(tmp_path: Path) -> None:
    handoff_json = tmp_path / "handoff.json"
    metrics = ["GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity", "DockQ", "ICS", "IPS"]
    current = _handoff_row(tmp_path, "H9002_Complex", "current_chain_A", metrics)
    freeze = _handoff_row(
        tmp_path,
        "H9002_Complex",
        "massivefold_model1_candidate",
        metrics,
        lane="massivefold_freeze_candidate",
    )
    _write_json(
        handoff_json,
        {
            "summary": {
                "metric_handoff_status": (
                    "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap"
                ),
                "out_dir": str(tmp_path / "handoff"),
            },
            "protein_rows": [
                {
                    "atlas_protein_key": "H9002_Complex",
                    "handoff_protein_folder": str(tmp_path / "handoff" / "H9002_Complex"),
                    "handoff_protein_manifest": str(
                        tmp_path / "handoff" / "H9002_Complex" / "protein_metric_handoff_manifest.json"
                    ),
                }
            ],
            "rows": [current, freeze],
        },
    )
    args = mod.parse_args(
        [
            "--metric-handoff-json",
            str(handoff_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
            "--out-html",
            str(tmp_path / "audit.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["metric_handoff_completion_audit_status"] == (
        "casp17_3d_molecular_object_metric_handoff_completion_audit_pass"
    )
    assert summary["protein_count"] == 1
    assert summary["protein_folder_present_count"] == 1
    assert summary["protein_readme_present_count"] == 1
    assert summary["protein_manifest_present_count"] == 1
    assert summary["object_pass_count"] == 2
    assert summary["object_blocked_count"] == 0
    assert summary["current_object_count"] == 1
    assert summary["massivefold_freeze_object_count"] == 1
    assert summary["handoff_object_folder_present_count"] == 2
    assert summary["handoff_object_manifest_present_count"] == 2
    assert summary["metric_requirements_csv_present_count"] == 2
    assert summary["metric_handoff_md_present_count"] == 2
    assert summary["metric_requirement_count"] == 18
    assert summary["metric_requirement_csv_row_count"] == 18
    assert summary["metric_requirement_csv_mismatch_count"] == 0
    assert summary["metric_evidence_awaiting_count"] == 2
    assert summary["object_coordinate_copy_count"] == 0
    assert summary["out_dir_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert {row["audit_status"] for row in payload["rows"]} == {"pass"}
    assert (tmp_path / "audit.json").is_file()
    assert (tmp_path / "AUDIT.md").is_file()
    assert "AUTHOR " not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_metric_handoff_completion_audit_blocks_missing_csv_and_coordinate_copy(
    tmp_path: Path,
) -> None:
    handoff_json = tmp_path / "handoff.json"
    metrics = ["GDT_TS", "lDDT"]
    row = _handoff_row(tmp_path, "T9999_Blocked", "current_chain_A", metrics)
    Path(row["metric_requirements_csv"]).unlink()
    _touch(Path(row["handoff_object_folder"]) / "copied_model.pdb", "ATOM copied\n")
    _write_json(
        handoff_json,
        {
            "summary": {
                "metric_handoff_status": "casp17_3d_molecular_object_metric_handoff_ready_review_only",
                "out_dir": str(tmp_path / "handoff"),
            },
            "protein_rows": [],
            "rows": [row],
        },
    )
    args = mod.parse_args(["--metric-handoff-json", str(handoff_json)])
    payload = mod.build_payload(args)

    assert payload["summary"]["metric_handoff_completion_audit_status"] == (
        "casp17_3d_molecular_object_metric_handoff_completion_audit_blocked"
    )
    assert payload["summary"]["object_blocked_count"] == 1
    assert payload["summary"]["object_coordinate_copy_count"] == 1
    assert payload["summary"]["out_dir_coordinate_copy_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "metric_requirements_csv_missing" in blockers
    assert "metric_requirement_csv_row_count_mismatch" in blockers
    assert "metric_requirement_csv_names_mismatch" in blockers
    assert "handoff_coordinate_copy_present" in blockers
