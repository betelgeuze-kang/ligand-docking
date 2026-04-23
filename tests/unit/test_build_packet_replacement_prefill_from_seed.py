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


def test_build_packet_replacement_prefill_from_seed_ca2(tmp_path: Path) -> None:
    replacement_csv = tmp_path / "runs" / "ca2_packet_replacement_workbook_current.csv"
    seed_csv = tmp_path / "runs" / "ca2_curated_candidate_source_seed_current.csv"
    _write_csv(
        replacement_csv,
        ["packet", "packet_step", "current_ligand_id"],
        [["core", "core_binder_01", "ca2_placeholder_binder_01"]],
    )
    _write_csv(
        seed_csv,
        [
            "packet_step",
            "candidate_ligand_name",
            "candidate_source_kind",
            "candidate_reference_hint",
            "target_anchor_pdb_id",
            "target_anchor_native_path",
            "candidate_status",
            "manual_verification_required",
            "next_action",
        ],
        [[
            "core_binder_01",
            "acetazolamide",
            "known_ca2_inhibitor_seed",
            "hint",
            "1CA2",
            "data/public_structures/1CA2.pdb",
            "suggested_not_applied",
            "yes",
            "verify",
        ]],
    )
    out_json = tmp_path / "runs" / "ca2_packet_replacement_prefill_current.json"
    out_csv = tmp_path / "runs" / "ca2_packet_replacement_prefill_current.csv"
    out_md = tmp_path / "runs" / "ca2_packet_replacement_prefill_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_packet_replacement_prefill_from_seed.py"),
            "--family",
            "ca2",
            "--replacement-csv",
            str(replacement_csv),
            "--seed-csv",
            str(seed_csv),
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
    assert payload["summary"]["matched_prefill_row_count"] == 1
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["candidate_ligand_name"] == "acetazolamide"
    assert rows[0]["prefill_status"] == "seed_attached"


def test_build_packet_replacement_prefill_from_seed_pxr(tmp_path: Path) -> None:
    replacement_csv = tmp_path / "runs" / "pxr_packet_replacement_workbook_current.csv"
    seed_csv = tmp_path / "runs" / "pxr_curated_candidate_source_seed_current.csv"
    _write_csv(
        replacement_csv,
        ["packet", "packet_step", "current_ligand_id"],
        [["ood", "ood_eval_binder_02", "pxr_ood_ligand_02"]],
    )
    _write_csv(
        seed_csv,
        [
            "packet_step",
            "candidate_ligand_name",
            "candidate_source_kind",
            "candidate_reference_hint",
            "target_anchor_pdb_id",
            "target_anchor_native_path",
            "candidate_status",
            "manual_verification_required",
            "next_action",
        ],
        [[
            "ood_eval_binder_02",
            "troglitazone",
            "known_pxr_ligand_seed",
            "hint",
            "O75469",
            "data/native/o75469.pdb",
            "suggested_not_applied",
            "yes",
            "verify",
        ]],
    )
    out_json = tmp_path / "runs" / "pxr_packet_replacement_prefill_current.json"
    out_csv = tmp_path / "runs" / "pxr_packet_replacement_prefill_current.csv"
    out_md = tmp_path / "runs" / "pxr_packet_replacement_prefill_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_packet_replacement_prefill_from_seed.py"),
            "--family",
            "pxr",
            "--replacement-csv",
            str(replacement_csv),
            "--seed-csv",
            str(seed_csv),
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
    assert payload["summary"]["matched_prefill_row_count"] == 1
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["candidate_ligand_name"] == "troglitazone"
    assert rows[0]["prefill_status"] == "seed_attached"
