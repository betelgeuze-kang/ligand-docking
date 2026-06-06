from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_authoritative_chronology_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_authoritative_chronology_audit_blocks_post_native_prediction_rows(tmp_path: Path) -> None:
    native_json = tmp_path / "native.json"
    chronology_json = tmp_path / "chronology.json"
    audit_dir = tmp_path / "audit"
    out_json = tmp_path / "audit.json"
    out_csv = tmp_path / "audit.csv"
    out_md = tmp_path / "AUDIT.md"

    _write_json(
        native_json,
        {
            "rows": [
                {
                    "target_id": "HIST_PRE",
                    "benchmark_id": "hist_pre",
                    "scope": "monomer",
                    "native_authority_status": "authority_pass",
                    "native_authority_ref": "rcsb:9PRE;doi:10.2210/pdb9pre/pdb",
                    "native_header": "HEADER    TEST PROTEIN                           02-JAN-26   9PRE",
                    "prediction_pdb": "runs/nightly/2026-01-01/pre_model.pdb",
                },
                {
                    "target_id": "HIST_POST",
                    "benchmark_id": "hist_post",
                    "scope": "monomer",
                    "native_authority_status": "authority_pass",
                    "native_authority_ref": "rcsb:1UAO;doi:10.2210/pdb1uao/pdb",
                    "native_header": "HEADER    DE NOVO PROTEIN                         13-MAR-03   1UAO",
                    "prediction_pdb": "runs/nightly/2026-02-19/post_model.pdb",
                },
                {
                    "target_id": "HIST_COMPLEX",
                    "benchmark_id": "hist_complex",
                    "scope": "complex",
                    "native_authority_status": "authority_blocked",
                    "native_authority_ref": "",
                    "native_header": "",
                    "prediction_pdb": "runs/current/complex_model.pdb",
                },
            ]
        },
    )
    _write_json(
        chronology_json,
        {
            "rows": [
                {"target_id": "HIST_PRE", "prediction_path_date": "2026-01-01"},
                {"target_id": "HIST_POST", "prediction_path_date": "2026-02-19"},
            ]
        },
    )

    args = mod.parse_args(
        [
            "--native-authority-audit-json",
            str(native_json),
            "--chronology-board-json",
            str(chronology_json),
            "--audit-dir",
            str(audit_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["authoritative_chronology_audit_status"] == (
        "post_native_prediction_chronology_blocked"
    )
    assert payload["summary"]["seed_row_count"] == 3
    assert payload["summary"]["native_authority_date_count"] == 2
    assert payload["summary"]["prediction_date_candidate_count"] == 2
    assert payload["summary"]["before_native_candidate_count"] == 1
    assert payload["summary"]["post_native_blocked_count"] == 1
    assert payload["summary"]["evidence_required_count"] == 1
    assert payload["summary"]["native_authority_not_pass_count"] == 1
    assert payload["summary"]["missing_native_authority_date_count"] == 1
    assert payload["summary"]["missing_prediction_date_count"] == 1

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["HIST_PRE"]["chronology_authority_status"] == "chronology_candidate_before_native_review"
    assert rows["HIST_PRE"]["native_authority_date"] == "2026-01-02"
    assert rows["HIST_POST"]["chronology_authority_status"] == "post_native_prediction_chronology_blocked"
    assert rows["HIST_POST"]["prediction_after_native_authority"] is True
    assert "prediction_not_before_authoritative_native_date" in rows["HIST_POST"]["blockers"]
    assert rows["HIST_COMPLEX"]["chronology_authority_status"] == (
        "operator_authoritative_chronology_evidence_required"
    )

    written_rows = _read_csv(out_csv)
    assert len(written_rows) == 3
    assert (audit_dir / "02_hist_post" / "AUTHORITATIVE_CHRONOLOGY.md").exists()
    assert "Claim Boundary" in out_md.read_text(encoding="utf-8")


def test_authoritative_chronology_audit_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(
            [
                "--native-authority-audit-json",
                str(tmp_path / "missing_native.json"),
                "--chronology-board-json",
                str(tmp_path / "missing_chronology.json"),
                "--audit-dir",
                str(tmp_path / "audit"),
            ]
        )
    )

    assert payload["summary"]["authoritative_chronology_audit_status"] == "blocked_missing_input"
    assert "native_authority_audit_json_missing" in payload["summary"]["input_blockers"]
    assert "chronology_board_json_missing" in payload["summary"]["input_blockers"]
