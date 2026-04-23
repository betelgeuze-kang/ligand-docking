from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_build_packet_replacement_draft_apply_ca2(tmp_path: Path) -> None:
    prefill_csv = tmp_path / "runs" / "ca2_packet_replacement_prefill_current.csv"
    _write_csv(
        prefill_csv,
        ["packet_step", "current_ligand_id", "candidate_ligand_name", "candidate_source_kind", "candidate_anchor_pdb_id", "candidate_anchor_native_path", "prefill_status"],
        [["core_binder_01", "ca2_placeholder_binder_01", "acetazolamide", "known_ca2_inhibitor_seed", "1CA2", "data/public_structures/1CA2.pdb", "seed_attached"]],
    )
    out_json = tmp_path / "runs" / "ca2_packet_replacement_draft_apply_current.json"
    out_csv = tmp_path / "runs" / "ca2_packet_replacement_draft_apply_current.csv"
    out_md = tmp_path / "runs" / "ca2_packet_replacement_draft_apply_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools" / "build_packet_replacement_draft_apply.py"),
            "--family",
            "ca2",
            "--prefill-csv",
            str(prefill_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=tmp_path,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["candidate_attached_row_count"] == 1
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["draft_replacement_ligand_id"] == "acetazolamide"
    assert rows[0]["authoritative_replacement_fields_touched"] == "no"


def test_build_packet_replacement_draft_apply_pxr_seed_missing(tmp_path: Path) -> None:
    prefill_csv = tmp_path / "runs" / "pxr_packet_replacement_prefill_current.csv"
    _write_csv(
        prefill_csv,
        ["packet_step", "current_ligand_id", "candidate_ligand_name", "candidate_source_kind", "candidate_anchor_pdb_id", "candidate_anchor_native_path", "prefill_status"],
        [["ood_eval_binder_02", "pxr_ood_ligand_02", "", "", "O75469", "data/native/o75469.pdb", "seed_missing"]],
    )
    out_json = tmp_path / "runs" / "pxr_packet_replacement_draft_apply_current.json"
    out_csv = tmp_path / "runs" / "pxr_packet_replacement_draft_apply_current.csv"
    out_md = tmp_path / "runs" / "pxr_packet_replacement_draft_apply_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools" / "build_packet_replacement_draft_apply.py"),
            "--family",
            "pxr",
            "--prefill-csv",
            str(prefill_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=tmp_path,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["seed_missing_row_count"] == 1
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["draft_apply_status"] == "seed_missing"
    assert rows[0]["draft_can_promote_after_verification"] == "no"
