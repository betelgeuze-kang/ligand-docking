from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_representative_rerank_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_cif(path: Path, b_iso: float, offset: float = 0.0) -> None:
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
    atoms = [
        ("P", "P", "G", "A", "1", 0.0 + offset, 0.0, 0.0),
        ("O", "O5'", "G", "A", "1", 1.0 + offset, 0.0, 0.0),
        ("C", "C4'", "G", "A", "1", 1.0 + offset, 1.0, 0.0),
        ("N", "N9", "G", "A", "1", 1.0 + offset, 1.0, 1.0),
    ]
    for idx, (element, atom_name, res, chain, seq, x, y, z) in enumerate(atoms, start=1):
        atom_token = f'"{atom_name}"' if "'" in atom_name else atom_name
        lines.append(
            f"ATOM {idx} {element} {atom_token} . {res} {chain} 1 {seq} ? "
            f"{x:.3f} {y:.3f} {z:.3f} 1.00 {b_iso:.2f} {seq} {chain} 1"
        )
    lines.append("#")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_massivefold_representative_rerank_selects_model1_and_protocol_balanced_top5(tmp_path: Path) -> None:
    protocols = ["basic", "woTemplates", "woUnpaired", "woPaired", "woUnpaired_woPaired", "basic"]
    b_values = [82.0, 81.0, 80.0, 79.0, 78.0, 95.0]
    rows = []
    for index, (protocol, b_iso) in enumerate(zip(protocols, b_values), start=1):
        cif = tmp_path / f"viewers/r2341/selection_{index:03d}_{protocol}/model.cif"
        _write_cif(cif, b_iso=b_iso, offset=float(index))
        rows.append(
            {
                "target_id": "R2341",
                "selection_rank": index,
                "model_serial": index,
                "filename": f"Model_{index}_af3_{protocol}.cif",
                "rerank_bucket": protocol,
                "seed": 100 + index,
                "sample": index % 5,
                "pred": 200 + index,
                "model_viewer_status": "pass",
                "model_cif_path": str(cif),
                "viewer_html_path": str(cif.parent / "viewer.html"),
                "projection_svg_path": str(cif.parent / "projection.svg"),
                "model_review_md_path": str(cif.parent / "MODEL_REVIEW.md"),
                "radius_of_gyration": 2.0,
                "bbox_diagonal": 3.0,
                "centroid_x": 0.0,
                "centroid_y": 0.0,
                "centroid_z": 0.0,
            }
        )
    viewer_json = tmp_path / "viewer.json"
    _write_json(
        viewer_json,
        {
            "summary": {
                "massivefold_representative_viewer_status": "massivefold_representative_viewers_ready"
            },
            "rows": rows,
        },
    )
    args = mod.parse_args(
        [
            "--viewer-packet-json",
            str(viewer_json),
            "--target-id",
            "R2341",
            "--out-dir",
            str(tmp_path / "rerank"),
            "--out-json",
            str(tmp_path / "rerank.json"),
            "--out-csv",
            str(tmp_path / "rerank.csv"),
            "--out-md",
            str(tmp_path / "RERANK.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_representative_rerank_status"] == (
        "massivefold_representative_rerank_ready_review_only"
    )
    assert summary["candidate_count"] == 6
    assert summary["model1_candidate_count"] == 1
    assert summary["top5_candidate_count"] == 5
    assert summary["top5_protocol_count"] == 5
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["model1_filename"] == "Model_6_af3_basic.cif"
    assert summary["model1_protocol"] == "basic"

    by_top5_rank = {
        int(row["top5_selection_rank"]): row
        for row in payload["rows"]
        if int(row["top5_selection_rank"])
    }
    assert by_top5_rank[1]["model1_candidate"] is True
    assert by_top5_rank[1]["quality_rank"] == 1
    assert sorted(by_top5_rank) == [1, 2, 3, 4, 5]
    assert len({row["rerank_bucket"] for row in by_top5_rank.values()}) == 5
    for row in by_top5_rank.values():
        folder = Path(row["rerank_model_folder"])
        assert (folder / "model.cif").is_file()
        assert (folder / "MODEL_SELECTION.md").is_file()
    assert len(_read_csv(tmp_path / "rerank.csv")) == 6
    assert len(_read_csv(Path(summary["top5_manifest_csv"]))) == 5
    assert "candidates/model1/top5: `6/1/5`" in (tmp_path / "RERANK.md").read_text(encoding="utf-8")


def test_massivefold_representative_rerank_blocks_missing_viewer_packet(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--viewer-packet-json",
            str(tmp_path / "missing_viewer.json"),
            "--target-id",
            "R2341",
            "--out-dir",
            str(tmp_path / "rerank"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_representative_rerank_status"] == (
        "blocked_massivefold_representative_viewer_packet_missing"
    )
    assert payload["summary"]["candidate_count"] == 0
    assert payload["summary"]["top5_candidate_count"] == 0
