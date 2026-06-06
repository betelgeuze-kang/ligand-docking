from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_validate_pxr_packet_fill_readiness(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    queue_json = runs / "pxr_packet_fill_queue_current.json"
    ligand_json = runs / "pxr_ligand_packet_fill_workbook_current.json"
    replacement_csv = runs / "pxr_packet_replacement_workbook_current.csv"

    _write_json(
        queue_json,
        {
            "target": "PXR_NR1I2_BLIND",
            "queue_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "pxr_fit_ligand_01",
                    "current_role": "fit",
                    "placeholder_sources": "reference,meta",
                },
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "pxr_eval_ligand_01",
                    "current_role": "far_ood_eval",
                    "placeholder_sources": "reference,meta",
                },
            ],
        },
    )
    _write_json(
        ligand_json,
        {
            "workbook_rows": [
                {
                    "packet": "core",
                    "ligand_id": "pxr_fit_ligand_01",
                    "role": "fit",
                },
                {
                    "packet": "core",
                    "ligand_id": "pxr_eval_ligand_01",
                    "role": "far_ood_eval",
                },
            ]
        },
    )
    _write_csv(
        replacement_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
            "replacement_role",
            "required_missing_fields",
            "row_ready_for_apply",
        ],
        [
            ["core", "core_binder_01", "pxr_fit_ligand_01", "fit", "", "yes"],
            [
                "core",
                "core_binder_01",
                "pxr_eval_ligand_01",
                "far_ood_eval",
                "replacement_smiles,replacement_scaffold",
                "no",
            ],
        ],
    )

    out_json = runs / "pxr_packet_fill_readiness_current.json"
    out_csv = runs / "pxr_packet_fill_readiness_current.csv"
    out_md = runs / "pxr_packet_fill_readiness_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/validate_pxr_packet_fill_readiness.py"),
            "--queue-json",
            str(queue_json),
            "--ligand-workbook-json",
            str(ligand_json),
            "--replacement-csv",
            str(replacement_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["matched_queue_rows"] == 2
    assert payload["summary"]["ready_for_apply_row_count"] == 1
    assert payload["summary"]["duplicate_packet_step_count"] == 1
    assert payload["summary"]["most_common_missing_field"] == "replacement_smiles"

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert {row["queue_row_key"] for row in rows} == {
        "core|fit|pxr_fit_ligand_01",
        "core|far_ood_eval|pxr_eval_ligand_01",
    }
    assert any(row["ready_for_apply"] == "yes" for row in rows)
    assert any(row["packet_step_duplicate_in_queue"] == "yes" for row in rows)

    md_text = out_md.read_text(encoding="utf-8")
    assert "PXR Packet Fill Readiness" in md_text
    assert "duplicate_packet_step_count" in md_text


def test_validate_pxr_packet_fill_readiness_uses_completed_workbook_when_queue_empty(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    queue_json = runs / "pxr_packet_fill_queue_current.json"
    ligand_json = runs / "pxr_ligand_packet_fill_workbook_current.json"
    replacement_csv = runs / "pxr_packet_replacement_workbook_current.csv"

    _write_json(
        queue_json,
        {
            "target": "PXR_NR1I2_BLIND",
            "queue_rows": [],
        },
    )
    _write_json(
        ligand_json,
        {
            "workbook_rows": [
                {
                    "packet": "core",
                    "ligand_id": "chembl242526",
                    "role": "far_ood_eval",
                },
                {
                    "packet": "core",
                    "ligand_id": "rifampicin",
                    "role": "fit",
                },
            ]
        },
    )
    _write_csv(
        replacement_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
            "replacement_ligand_id",
            "replacement_role",
            "required_missing_fields",
            "row_ready_for_apply",
        ],
        [
            [
                "core",
                "core_eval_non_binder_01",
                "pxr_decoy_ligand_01",
                "chembl242526",
                "far_ood_eval",
                "",
                "yes",
            ],
            [
                "core",
                "core_fit_binder_01",
                "rifampicin",
                "rifampicin",
                "fit",
                "",
                "yes",
            ],
        ],
    )

    out_json = runs / "pxr_packet_fill_readiness_current.json"
    out_csv = runs / "pxr_packet_fill_readiness_current.csv"
    out_md = runs / "pxr_packet_fill_readiness_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/validate_pxr_packet_fill_readiness.py"),
            "--queue-json",
            str(queue_json),
            "--ligand-workbook-json",
            str(ligand_json),
            "--replacement-csv",
            str(replacement_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["source_queue_row_count"] == 0
    assert payload["summary"]["queue_row_count"] == 2
    assert payload["summary"]["queue_empty_fallback_from_replacement_workbook"] is True
    assert payload["summary"]["matched_queue_rows"] == 2
    assert payload["summary"]["ready_for_apply_row_count"] == 2
    assert payload["summary"]["blocked_row_count"] == 0
    assert payload["summary"]["next_required_step"] == (
        "All replacement workbook rows are ready for authoritative PXR packet apply."
    )

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert {row["queue_source"] for row in rows} == {"replacement_workbook_fallback"}
    assert all(row["ligand_workbook_row_present"] == "yes" for row in rows)
