from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_massivefold_representative_viewer_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_cif(path: Path, atoms: list[tuple[str, str, str, str, str, float, float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "data_model",
        "#",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_alt_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_entity_id",
        "_atom_site.label_seq_id",
        "_atom_site.pdbx_PDB_ins_code",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.auth_seq_id",
        "_atom_site.auth_asym_id",
        "_atom_site.pdbx_PDB_model_num",
    ]
    for idx, (element, atom_name, res, chain, seq, x, y, z, b_iso) in enumerate(atoms, start=1):
        atom_token = f'"{atom_name}"' if "'" in atom_name else atom_name
        lines.append(
            f"ATOM {idx} {element} {atom_token} . {res} {chain} 1 {seq} ? "
            f"{x:.3f} {y:.3f} {z:.3f} 1.00 {b_iso:.2f} {seq} {chain} 1"
        )
    lines.append("#")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_pdb(path: Path, atoms: list[tuple[str, str, str, str, int, float, float, float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for serial, (element, atom_name, res, chain, seq, x, y, z, b_iso) in enumerate(atoms, start=1):
        lines.append(
            f"ATOM  {serial:5d} {atom_name:<4} {res:>3} {chain:1}{seq:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_iso:6.2f}          {element:>2}"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_massivefold_representative_viewer_packet_builds_local_model_folders(tmp_path: Path) -> None:
    cif1 = tmp_path / "pool/R2341_all_cifs/Model_1_af3_basic_af3_seed_101_sample_0_pred_10.cif"
    cif2 = tmp_path / "pool/R2341_all_cifs/Model_2_af3_woTemplates_af3_seed_102_sample_1_pred_11.cif"
    _write_cif(
        cif1,
        [
            ("P", "P", "G", "A", "1", 0.0, 0.0, 0.0, 70.0),
            ("O", "O5'", "G", "A", "1", 1.0, 0.0, 0.0, 71.0),
            ("C", "C4'", "G", "A", "1", 1.0, 1.0, 0.0, 72.0),
            ("N", "N9", "G", "A", "1", 1.0, 1.0, 1.0, 73.0),
        ],
    )
    _write_cif(
        cif2,
        [
            ("P", "P", "C", "A", "2", 2.0, 0.0, 0.0, 65.0),
            ("O", "OP1", "C", "A", "2", 2.0, 2.0, 0.0, 66.0),
        ],
    )
    index_json = tmp_path / "index.json"
    _write_json(
        index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": "massivefold_model_pool_representatives_extracted",
                "target_id": "R2341",
            },
            "rows": [
                {
                    "target_id": "R2341",
                    "model_set_id": "R2341",
                    "selection_rank": 1,
                    "model_serial": 1,
                    "filename": cif1.name,
                    "rerank_bucket": "basic",
                    "seed": 101,
                    "sample": 0,
                    "pred": 10,
                    "selected_for_balanced_extract": "True",
                    "extract_destination": str(cif1),
                },
                {
                    "target_id": "R2341",
                    "model_set_id": "R2341",
                    "selection_rank": 2,
                    "model_serial": 2,
                    "filename": cif2.name,
                    "rerank_bucket": "woTemplates",
                    "seed": 102,
                    "sample": 1,
                    "pred": 11,
                    "selected_for_balanced_extract": "True",
                    "extract_destination": str(cif2),
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--model-pool-index-json",
            str(index_json),
            "--target-id",
            "R2341",
            "--max-display-atoms",
            "3",
            "--out-dir",
            str(tmp_path / "viewers"),
            "--out-json",
            str(tmp_path / "viewer.json"),
            "--out-csv",
            str(tmp_path / "viewer.csv"),
            "--out-md",
            str(tmp_path / "VIEWERS.md"),
            "--out-html",
            str(tmp_path / "gallery.html"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_representative_viewer_status"] == "massivefold_representative_viewers_ready"
    assert summary["selected_model_count"] == 2
    assert summary["viewer_ready_count"] == 2
    assert summary["coordinate_valid_count"] == 2
    assert summary["model_cif_present_count"] == 2
    assert summary["projection_ready_count"] == 2
    assert summary["atom_count_total"] == 6
    assert summary["display_atom_count_total"] == 5
    assert summary["protocol_bucket_count"] == 2

    rows = payload["rows"]
    assert rows[0]["atom_count"] == 4
    assert rows[0]["display_atom_count"] == 3
    assert rows[0]["residue_count"] == 1
    assert Path(rows[0]["object_folder"]).is_dir()
    for row in rows:
        folder = Path(row["object_folder"])
        assert (folder / "model.cif").is_file()
        assert (folder / "projection.svg").read_text(encoding="utf-8").startswith("<svg")
        viewer = (folder / "viewer.html").read_text(encoding="utf-8")
        assert '<canvas id="viewer"' in viewer
        assert "const atoms =" in viewer
        assert "requestAnimationFrame" in viewer
        assert "http://" not in viewer
        assert "https://" not in viewer
        assert (folder / "MODEL_REVIEW.md").is_file()
        assert (folder / "source_model_row.csv").is_file()
    assert len(_read_csv(tmp_path / "viewer.csv")) == 2
    assert "selected/viewers/blocked: `2/2/0`" in (tmp_path / "VIEWERS.md").read_text(encoding="utf-8")
    assert "CASP17 MassiveFold Representative Viewer Gallery" in (tmp_path / "gallery.html").read_text(
        encoding="utf-8"
    )


def test_massivefold_representative_viewer_packet_accepts_pdb_bundle_models(tmp_path: Path) -> None:
    pdb = tmp_path / "pool/H1311_T327_all_pdbs/Model_1_af3_basic_af3_seed_101_sample_0_pred_10.pdb"
    _write_pdb(
        pdb,
        [
            ("N", "N", "GLY", "A", 1, 0.0, 0.0, 0.0, 50.0),
            ("C", "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, 51.0),
            ("C", "C", "SER", "A", 2, 1.0, 1.0, 0.0, 52.0),
            ("O", "O", "SER", "A", 2, 1.0, 1.0, 1.0, 53.0),
        ],
    )
    index_json = tmp_path / "index.json"
    _write_json(
        index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": "massivefold_model_pool_representatives_extracted",
                "target_id": "H1311",
            },
            "rows": [
                {
                    "target_id": "H1311",
                    "model_set_id": "H1311_T327",
                    "selection_rank": 1,
                    "model_serial": 1,
                    "filename": pdb.name,
                    "rerank_bucket": "basic",
                    "seed": 101,
                    "sample": 0,
                    "pred": 10,
                    "selected_for_balanced_extract": "True",
                    "extract_destination": str(pdb),
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--model-pool-index-json",
            str(index_json),
            "--target-id",
            "H1311",
            "--max-display-atoms",
            "4",
            "--out-dir",
            str(tmp_path / "viewers"),
            "--out-json",
            str(tmp_path / "viewer.json"),
            "--out-csv",
            str(tmp_path / "viewer.csv"),
            "--out-md",
            str(tmp_path / "VIEWERS.md"),
            "--out-html",
            str(tmp_path / "gallery.html"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_representative_viewer_status"] == "massivefold_representative_viewers_ready"
    assert summary["selected_model_count"] == 1
    assert summary["viewer_ready_count"] == 1
    assert summary["coordinate_valid_count"] == 1
    assert summary["atom_count_total"] == 4
    assert summary["residue_count_total"] == 2
    assert summary["chain_count_max"] == 1

    row = payload["rows"][0]
    assert row["model_viewer_status"] == "pass"
    assert row["coordinate_status"] == "valid"
    assert row["atom_count"] == 4
    assert row["residue_count"] == 2
    assert row["chain_count"] == 1
    assert row["blockers"] == ""
    folder = Path(row["object_folder"])
    assert (folder / "model.cif").read_text(encoding="utf-8").startswith("ATOM")
    assert (folder / "projection.svg").is_file()
    assert (folder / "viewer.html").is_file()
    assert len(_read_csv(tmp_path / "viewer.csv")) == 1


def test_massivefold_representative_viewer_packet_blocks_missing_selected_cif(tmp_path: Path) -> None:
    missing_cif = tmp_path / "pool/R2341_all_cifs/missing.cif"
    index_json = tmp_path / "index.json"
    _write_json(
        index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": "massivefold_model_pool_representatives_extracted"
            },
            "rows": [
                {
                    "target_id": "R2341",
                    "model_set_id": "R2341",
                    "selection_rank": 1,
                    "model_serial": 1,
                    "filename": missing_cif.name,
                    "rerank_bucket": "basic",
                    "seed": 101,
                    "sample": 0,
                    "pred": 10,
                    "selected_for_balanced_extract": "True",
                    "extract_destination": str(missing_cif),
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--model-pool-index-json",
            str(index_json),
            "--target-id",
            "R2341",
            "--out-dir",
            str(tmp_path / "viewers"),
        ]
    )

    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["massivefold_representative_viewer_status"] == "blocked_massivefold_representative_viewers"
    assert summary["viewer_ready_count"] == 0
    assert summary["viewer_blocked_count"] == 1
    assert summary["coordinate_valid_count"] == 0
    assert summary["first_blocked_model"] == "missing.cif"
    assert "model_cif_source_missing" in summary["first_blocked_blockers"]
    assert "coordinates_missing" in payload["rows"][0]["blockers"]
