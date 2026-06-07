from __future__ import annotations

import csv
import json
from pathlib import Path

from betelgeuze_cameo.format_validation import build_format_validation_packet, validate_model_file
from tools import build_cameo_format_validation_packet as tool


def _pdb_atom(serial: int, atom: str, residue: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}{residue:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.0:6.2f}           C  "
    )


def test_validate_cameo_pdb_model_passes_minimal_model(tmp_path: Path) -> None:
    model = tmp_path / "model1.pdb"
    model.write_text(
        "\n".join(
            [
                "MODEL        1",
                _pdb_atom(1, "N", "ALA", "A", 1, 1.0, 2.0, 3.0),
                _pdb_atom(2, "CA", "ALA", "A", 1, 2.0, 2.0, 3.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    payload = validate_model_file(model, target_id="CAMEO001", candidate_id="internal_a", cameo_model_rank=1)

    assert payload["summary"]["format_validation_status"] == "pass"
    assert payload["summary"]["detected_format"] == "pdb"
    assert payload["summary"]["atom_count"] == 2
    assert payload["summary"]["model_indices"] == [1]
    assert payload["summary"]["native_or_external_accuracy_used"] is False
    assert payload["summary"]["outbound_email_enabled"] is False


def test_validate_cameo_pdb_model_fails_without_atoms(tmp_path: Path) -> None:
    model = tmp_path / "bad_model.pdb"
    model.write_text("HEADER no coordinates\nEND\n", encoding="utf-8")

    payload = validate_model_file(model)
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["format_validation_status"] == "fail"
    assert "atom_records_missing" in codes


def test_validate_cameo_mmcif_model_passes_minimal_atom_site_loop(tmp_path: Path) -> None:
    model = tmp_path / "model1.cif"
    model.write_text(
        "\n".join(
            [
                "data_CAMEO001",
                "loop_",
                "_atom_site.group_PDB",
                "_atom_site.id",
                "_atom_site.type_symbol",
                "_atom_site.label_atom_id",
                "_atom_site.label_comp_id",
                "_atom_site.label_asym_id",
                "_atom_site.label_seq_id",
                "_atom_site.Cartn_x",
                "_atom_site.Cartn_y",
                "_atom_site.Cartn_z",
                "_atom_site.pdbx_PDB_model_num",
                "ATOM 1 C CA ALA A 1 1.000 2.000 3.000 1",
                "#",
                "",
            ]
        ),
        encoding="utf-8",
    )

    payload = validate_model_file(model, target_id="CAMEO001", candidate_id="internal_cif", cameo_model_rank=1)

    assert payload["summary"]["format_validation_status"] == "pass"
    assert payload["summary"]["detected_format"] == "mmcif"
    assert payload["summary"]["atom_count"] == 1
    assert payload["summary"]["chain_count"] == 1


def test_build_cameo_format_validation_packet_selects_top5_rows(tmp_path: Path) -> None:
    selected_model = tmp_path / "selected.pdb"
    rejected_model = tmp_path / "not_selected.pdb"
    selected_model.write_text("\n".join(["MODEL 1", _pdb_atom(1, "CA", "ALA", "A", 1, 1, 1, 1), "END", ""]), encoding="utf-8")
    rejected_model.write_text("HEADER no atoms\nEND\n", encoding="utf-8")

    payload = build_format_validation_packet(
        [
            {
                "target_id": "CAMEO002",
                "candidate_id": "selected",
                "model_path": "selected.pdb",
                "cameo_model_rank": "1",
            },
            {
                "target_id": "CAMEO002",
                "candidate_id": "not_selected",
                "model_path": "not_selected.pdb",
                "cameo_model_rank": "0",
            },
        ],
        target_id="CAMEO002",
        base_dir=tmp_path,
        selected_only=True,
    )

    assert payload["summary"]["status"] == "cameo_format_validation_ready"
    assert payload["summary"]["validated_model_count"] == 1
    assert payload["rows"][0]["candidate_id"] == "selected"


def test_build_cameo_format_validation_packet_tool(tmp_path: Path) -> None:
    model = tmp_path / "model.pdb"
    models_csv = tmp_path / "models.csv"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    model.write_text("\n".join(["MODEL 1", _pdb_atom(1, "CA", "ALA", "A", 1, 1, 1, 1), "END", ""]), encoding="utf-8")
    with models_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["target_id", "candidate_id", "model_path", "cameo_model_rank"])
        writer.writeheader()
        writer.writerow({"target_id": "CAMEO003", "candidate_id": "tool_model", "model_path": str(model), "cameo_model_rank": "1"})

    payload = tool.build_format_validation_packet(tool._read_csv_rows(models_csv), target_id="CAMEO003", base_dir=tmp_path)
    tool._write_json(out_json, payload)
    tool.write_csv_rows(out_csv, payload["rows"])
    tool._write_markdown(out_md, payload)

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_format_validation_ready"
    assert "CAMEO Format Validation Packet" in out_md.read_text(encoding="utf-8")
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,")


def test_validate_cameo_model_rank_above_top5_fails(tmp_path: Path) -> None:
    model = tmp_path / "rank6.pdb"
    model.write_text("\n".join(["MODEL 1", _pdb_atom(1, "CA", "ALA", "A", 1, 1, 1, 1), "END", ""]), encoding="utf-8")

    payload = validate_model_file(model, target_id="CAMEO004", candidate_id="rank6", cameo_model_rank=6)
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["format_validation_status"] == "fail"
    assert "cameo_model_rank_out_of_range" in codes
