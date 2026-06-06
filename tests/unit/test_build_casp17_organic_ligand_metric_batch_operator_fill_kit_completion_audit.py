import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
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


def _candidate(
    tmp_path: Path,
    root: Path,
    index: int,
    candidate_id: str,
    field_count: int,
) -> tuple[dict, list[dict]]:
    folder = root / f"{index:02d}_ligand_{index:03d}"
    rows = [
        {
            "fill_id": f"{candidate_id}_field_{field_index}",
            "candidate_rank": str(index),
            "candidate_id": candidate_id,
            "target_id": f"HIST_COMPLEX_{index:02d}",
            "ligand_id": f"ligand_{index:03d}",
            "field_order": str(field_index),
            "field_key": f"field_{field_index}",
            "fill_status": "operator_value_missing",
            "operator_value": "",
            "operator_evidence_ref": "",
            "operator_clearance": "",
            "operator_id": "",
            "source_operator_template_csv": str(tmp_path / "templates" / f"{candidate_id}.csv"),
            "source_evidence_stub_md": str(tmp_path / "stubs" / f"{candidate_id}_{field_index}.md"),
            "linked_action_md": str(tmp_path / "actions" / f"{candidate_id}_{field_index}.md"),
        }
        for field_index in range(1, field_count + 1)
    ]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(f"# {candidate_id}\n", encoding="utf-8")
    _write_csv(folder / "operator_fill_rows.csv", rows)
    candidate = {
        "candidate_id": candidate_id,
        "target_id": f"HIST_COMPLEX_{index:02d}",
        "ligand_id": f"ligand_{index:03d}",
        "field_count": field_count,
        "field_ready_count": 0,
        "field_blocked_count": field_count,
        "candidate_folder": str(folder),
        "candidate_operator_fill_csv": str(folder / "operator_fill_rows.csv"),
        "candidate_readme": str(folder / "README.md"),
    }
    return candidate, rows


def _kit_payload(tmp_path: Path) -> Path:
    root = tmp_path / "batch_kit"
    candidate_one, rows_one = _candidate(tmp_path, root, 1, "organic_ligand_slot_candidate_001", 3)
    candidate_two, rows_two = _candidate(tmp_path, root, 2, "organic_ligand_slot_candidate_002", 2)
    rows = rows_one + rows_two
    candidates = [candidate_one, candidate_two]
    _write_csv(root / "operator_fill_intake_batch.csv", rows)
    _write_csv(root / "candidate_summary.csv", candidates)
    (root / "RERUN_COMMANDS.md").write_text("# Rerun Commands\n", encoding="utf-8")
    summary = {
        "organic_ligand_metric_batch_operator_fill_kit_status": (
            "organic_ligand_metric_batch_operator_fill_kit_ready_for_operator_fill"
        ),
        "batch_folder": str(root),
        "operator_fill_intake_batch_csv": str(root / "operator_fill_intake_batch.csv"),
        "candidate_summary_csv": str(root / "candidate_summary.csv"),
        "rerun_commands_md": str(root / "RERUN_COMMANDS.md"),
        "batch_manifest_json": str(root / "batch_manifest.json"),
        "candidate_count": len(candidates),
        "field_count": len(rows),
    }
    _write_json(
        root / "batch_manifest.json",
        {
            "summary": summary,
            "candidate_rows": candidates,
            "rerun_commands": ["python3 tools/build_casp17_workbench_index.py"],
        },
    )
    kit_json = tmp_path / "kit.json"
    _write_json(kit_json, {"summary": summary, "rows": rows, "candidate_rows": candidates})
    return kit_json


def test_batch_operator_fill_kit_completion_audit_passes_complete_kit(tmp_path: Path) -> None:
    kit_json = _kit_payload(tmp_path)
    args = mod.parse_args(
        [
            "--batch-kit-json",
            str(kit_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_metric_batch_operator_fill_kit_completion_audit_status"] == (
        "casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_pass"
    )
    assert summary["candidate_pass_count"] == 2
    assert summary["candidate_blocked_count"] == 0
    assert summary["field_count"] == 5
    assert summary["batch_csv_row_count"] == 5
    assert summary["per_candidate_csv_row_count"] == 5
    assert summary["root_file_present_count"] == 4
    assert summary["candidate_folder_present_count"] == 2
    assert summary["candidate_readme_present_count"] == 2
    assert summary["candidate_operator_fill_csv_present_count"] == 2
    assert summary["coordinate_copy_count"] == 0
    assert summary["proof_marker_count"] == 0
    assert summary["author_marker_count"] == 0
    assert {row["audit_status"] for row in payload["rows"]} == {"pass"}
    assert (tmp_path / "audit.json").is_file()
    assert (tmp_path / "AUDIT.md").is_file()


def test_batch_operator_fill_kit_completion_audit_blocks_missing_csv_and_coordinate_copy(
    tmp_path: Path,
) -> None:
    kit_json = _kit_payload(tmp_path)
    payload = json.loads(kit_json.read_text(encoding="utf-8"))
    first_candidate = payload["candidate_rows"][0]
    Path(first_candidate["candidate_operator_fill_csv"]).unlink()
    (Path(first_candidate["candidate_folder"]) / "copied_model.pdb").write_text("ATOM copied\n", encoding="utf-8")

    args = mod.parse_args(["--batch-kit-json", str(kit_json)])
    audit = mod.build_payload(args)

    summary = audit["summary"]
    assert summary["organic_ligand_metric_batch_operator_fill_kit_completion_audit_status"] == (
        "casp17_organic_ligand_metric_batch_operator_fill_kit_completion_audit_blocked"
    )
    assert summary["candidate_blocked_count"] == 1
    assert summary["coordinate_copy_count"] == 1
    blockers = audit["rows"][0]["blockers"]
    assert "candidate_operator_fill_csv_missing" in blockers
    assert "candidate_operator_fill_csv_row_mismatch" in blockers
    assert "candidate_coordinate_copy_present" in blockers
