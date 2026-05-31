from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_native_authority_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_native_authority_audit_blocks_placeholder_ca_only_and_local_generated_native(tmp_path: Path) -> None:
    prediction = tmp_path / "prediction.pdb"
    prediction.write_text(
        "ATOM      1  N   ALA A   1       0.0   0.0   0.0  1.00 20.00           N\n"
        "ATOM      2  CA  ALA A   1       1.0   0.0   0.0  1.00 20.00           C\n",
        encoding="utf-8",
    )
    placeholder_native = tmp_path / "placeholder_native.pdb"
    placeholder_native.write_text(
        "HEADER    TEST NATIVE PLACEHOLDER\n"
        "TITLE     MINIMAL TEST STRUCTURE FOR VALIDATION\n"
        "ATOM      1  CA  ALA A   1       0.0   0.0   0.0  1.00 20.00           C\n",
        encoding="utf-8",
    )
    authoritative_native = tmp_path / "authoritative_native.pdb"
    authoritative_native.write_text(
        "HEADER    HYDROLASE                              01-JAN-00   1ABC\n"
        "TITLE     AUTHORITATIVE TEST STRUCTURE\n"
        "ATOM      1  N   ALA A   1       0.0   0.0   0.0  1.00 20.00           N\n"
        "ATOM      2  CA  ALA A   1       1.0   0.0   0.0  1.00 20.00           C\n"
        "ATOM      3  C   ALA A   1       2.0   0.0   0.0  1.00 20.00           C\n",
        encoding="utf-8",
    )
    local_complex_native = tmp_path / "local_complex_native.pdb"
    local_complex_native.write_text(authoritative_native.read_text(encoding="utf-8"), encoding="utf-8")
    seed_json = tmp_path / "seeds.json"
    _write_json(
        seed_json,
        {
            "rows": [
                {
                    "seed_rank": 1,
                    "batch_slot": 1,
                    "target_id": "HIST_PLACEHOLDER",
                    "benchmark_id": "hist_placeholder",
                    "scope": "monomer",
                    "prediction_pdb": str(prediction),
                    "native_pdb": str(placeholder_native),
                    "source_kind": "paired_native_internal_prediction",
                },
                {
                    "seed_rank": 2,
                    "batch_slot": 2,
                    "target_id": "HIST_AUTH",
                    "benchmark_id": "hist_auth",
                    "scope": "monomer",
                    "prediction_pdb": str(prediction),
                    "native_pdb": str(authoritative_native),
                    "source_kind": "paired_native_internal_prediction",
                    "native_authority_ref": "rcsb:1ABC",
                },
                {
                    "seed_rank": 3,
                    "batch_slot": 3,
                    "target_id": "HIST_LOCAL_COMPLEX",
                    "benchmark_id": "hist_local_complex",
                    "scope": "complex",
                    "prediction_pdb": str(prediction),
                    "native_pdb": str(local_complex_native),
                    "source_kind": "paired_protein_ligand_complex_minimized",
                },
            ]
        },
    )
    args = mod.parse_args(
        [
            "--seed-inventory-json",
            str(seed_json),
            "--audit-dir",
            str(tmp_path / "audit"),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["native_authority_audit_status"] == "blocked_native_authority"
    assert summary["native_authority_pass_count"] == 1
    assert summary["native_authority_blocked_count"] == 2
    assert summary["placeholder_native_count"] == 1
    assert summary["ca_only_native_count"] == 1
    assert summary["local_generated_native_without_authority_count"] == 1
    assert summary["authority_ref_missing_count"] == 2

    by_target = {row["target_id"]: row for row in _read_csv(tmp_path / "audit.csv")}
    assert by_target["HIST_AUTH"]["native_authority_status"] == "authority_pass"
    assert "native_placeholder_marker_present" in by_target["HIST_PLACEHOLDER"]["blockers"]
    assert "native_ca_only_no_sidechain_atoms" in by_target["HIST_PLACEHOLDER"]["blockers"]
    assert "local_generated_native_without_authority" in by_target["HIST_LOCAL_COMPLEX"]["blockers"]
    assert (tmp_path / "audit" / "01_hist_placeholder" / "NATIVE_AUTHORITY.md").exists()
