from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_native_replacement_candidates as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_native_replacement_candidates_copy_public_pdbs_and_hold_complexes(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    source = public_dir / "chignolin_pdb_1UAO.pdb"
    source.write_text(
        "HEADER    PEPTIDE                               01-JAN-04   1UAO\n"
        "TITLE     CHIGNOLIN\n"
        "ATOM      1  N   GLY A   1       0.0   0.0   0.0  1.00 20.00           N\n"
        "ATOM      2  CA  GLY A   1       1.0   0.0   0.0  1.00 20.00           C\n"
        "ATOM      3  C   GLY A   1       2.0   0.0   0.0  1.00 20.00           C\n",
        encoding="utf-8",
    )
    audit_json = tmp_path / "audit.json"
    _write_json(
        audit_json,
        {
            "rows": [
                {
                    "batch_slot": 2,
                    "target_id": "HIST_CHIGNOLIN",
                    "benchmark_id": "hist_seed_chignolin",
                    "scope": "monomer",
                },
                {
                    "batch_slot": 11,
                    "target_id": "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005",
                    "benchmark_id": "hist_seed_complex",
                    "scope": "complex",
                },
            ]
        },
    )
    args = mod.parse_args(
        [
            "--native-authority-audit-json",
            str(audit_json),
            "--public-structure-dir",
            str(public_dir),
            "--candidate-dir",
            str(tmp_path / "candidates"),
            "--out-json",
            str(tmp_path / "candidates.json"),
            "--out-csv",
            str(tmp_path / "candidates.csv"),
            "--out-md",
            str(tmp_path / "candidates.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["native_replacement_candidate_status"] == "partial_native_replacement_candidates_ready"
    assert summary["operator_review_ready_count"] == 1
    assert summary["complex_authority_required_count"] == 1
    assert summary["source_download_required_count"] == 0

    rows = _read_csv(tmp_path / "candidates.csv")
    by_target = {row["target_id"]: row for row in rows}
    chignolin = by_target["HIST_CHIGNOLIN"]
    assert chignolin["candidate_status"] == "operator_review_ready"
    assert chignolin["pdb_id"] == "1UAO"
    assert chignolin["candidate_atom_count"] == "3"
    assert chignolin["candidate_ca_only"] == "False"
    assert Path(chignolin["candidate_pdb"]).exists()
    assert "rcsb:1UAO" in chignolin["native_authority_ref"]

    complex_row = by_target["HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005"]
    assert complex_row["candidate_status"] == "native_authority_ref_required"
    assert "external_native_or_source_authority_required" in complex_row["blockers"]
    assert (tmp_path / "candidates" / "02_hist_chignolin" / "NATIVE_REPLACEMENT.md").exists()
