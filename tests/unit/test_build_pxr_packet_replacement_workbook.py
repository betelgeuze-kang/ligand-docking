from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_pxr_packet_replacement_workbook(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    queue_json = runs / "pxr_packet_fill_queue_current.json"
    _write_json(
        queue_json,
        {
            "target": "PXR_NR1I2_BLIND",
            "summary": {"queue_count": 2},
            "queue_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "pxr_fit_ligand_01",
                    "binder_label": "binder",
                    "current_role": "fit",
                    "current_reference_binding_kcal_mol": "TODO_BINDING_KCAL",
                    "current_source": "pxr_blind_proxy_v1",
                    "current_smiles": "TODO_SMILES",
                    "current_scaffold": "TODO_SCAFFOLD",
                    "placeholder_sources": "reference,meta",
                    "replacement_role": "fit",
                    "notes": "Replace placeholder core binder slot 01.",
                },
                {
                    "packet": "ood",
                    "packet_step": "ood_non_binder_01",
                    "current_ligand_id": "pxr_ood_decoy_01",
                    "binder_label": "non_binder",
                    "current_role": "far_ood_eval",
                    "current_reference_binding_kcal_mol": "TODO_BINDING_KCAL",
                    "current_source": "pxr_ood_proxy_v1",
                    "current_smiles": "TODO_SMILES",
                    "current_scaffold": "TODO_SCAFFOLD",
                    "placeholder_sources": "reference,meta",
                    "replacement_role": "far_ood_eval",
                    "notes": "Replace placeholder ood non-binder slot 01.",
                },
            ],
        },
    )

    out_json = runs / "pxr_packet_replacement_workbook_current.json"
    out_csv = runs / "pxr_packet_replacement_workbook_current.csv"
    out_md = runs / "pxr_packet_replacement_workbook_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/product/build_pxr_packet_replacement_workbook.py"),
            "--queue-json",
            str(queue_json),
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
    assert payload["summary"]["workbook_row_count"] == 2
    assert payload["summary"]["ready_seed_row_count"] == 0

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["target"] == "PXR_NR1I2_BLIND"
    assert rows[0]["replacement_is_binder"] == "1"
    assert rows[1]["replacement_is_binder"] == "0"
    assert "replacement_ligand_id" in rows[0]["required_missing_fields"]
    assert "replacement_smiles" in rows[0]["required_missing_fields"]

    md_text = out_md.read_text(encoding="utf-8")
    assert "PXR Packet Replacement Workbook" in md_text
    assert "core_binder_01" in md_text
