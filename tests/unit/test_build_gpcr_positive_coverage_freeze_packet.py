from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_positive_coverage_freeze_packet as mod

ROOT = Path(__file__).resolve().parents[2]


FIELDS = [
    "target",
    "ligand_id",
    "target_family",
    "is_binder",
    "reference_binding_kcal_mol",
    "source",
    "source_url",
    "source_release",
    "provenance_date",
    "smiles",
    "scaffold",
    "role",
    "curation_status",
    "leakage_audit_id",
    "notes",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _coverage(observed: int = 6) -> dict:
    return {
        "summary": {"observed_positive_count": observed},
        "stage5_context": {"positive_target_counts": {"ADRB2_GPCR_BLIND": observed}},
    }


def _audit(pass_: bool = True, **overrides: int) -> dict:
    payload = {
        "pass": pass_,
        "key_overlap_count": 0,
        "target_overlap_count": 0,
        "ligand_overlap_count": 0,
        "family_overlap_count": 0,
        "scaffold_overlap_count": 0,
        "sequence_leak_count": 0,
        "pocket_leak_count": 0,
        "failed_rules": [],
    }
    payload.update(overrides)
    if not pass_:
        payload["failed_rules"] = [{"metric": "key_overlap_count", "value": 1, "threshold": 0}]
    return payload


def _candidate(target: str, ligand_id: str) -> dict[str, str]:
    return {
        "target": target,
        "ligand_id": ligand_id,
        "target_family": "gpcr",
        "is_binder": "1",
        "reference_binding_kcal_mol": "-9.2",
        "source": "curated_non_adrb2_fixture",
        "source_url": "https://example.invalid/evidence",
        "source_release": "fixture",
        "provenance_date": "2026-05-03",
        "smiles": "CCN",
        "scaffold": "fixture_scaffold",
        "role": "far_ood_eval",
        "curation_status": "curated",
        "leakage_audit_id": "fixture_audit",
        "notes": "unit test fixture",
    }


def test_default_empty_schema_blocks_freeze(tmp_path: Path) -> None:
    candidates = tmp_path / "config" / "gpcr_non_adrb2_positive_candidates_v1.csv"
    audit = tmp_path / "runs" / "audit.json"
    coverage = tmp_path / "runs" / "coverage.json"
    _write_csv(candidates, [])
    _write_json(audit, _audit(True))
    _write_json(coverage, _coverage(6))

    payload = mod.build_packet(
        candidates_csv=candidates,
        leakage_audit_json=audit,
        positive_coverage_json=coverage,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["frozen"] is False
    assert payload["summary"]["positive_count"] == 6
    assert "candidate_csv_empty" in payload["summary"]["blockers"]
    assert "new_non_adrb2_positive_count_below_3" in payload["summary"]["blockers"]
    assert payload["summary"]["claim_promotion_allowed"] is False


def test_three_non_adrb2_gpcr_positives_with_clean_audit_freeze_packet(tmp_path: Path) -> None:
    candidates = tmp_path / "config" / "candidates.csv"
    audit = tmp_path / "runs" / "audit.json"
    coverage = tmp_path / "runs" / "coverage.json"
    _write_csv(
        candidates,
        [
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_1"),
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_2"),
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_3"),
        ],
    )
    _write_json(audit, _audit(True))
    _write_json(coverage, _coverage(6))

    payload = mod.build_packet(
        candidates_csv=candidates,
        leakage_audit_json=audit,
        positive_coverage_json=coverage,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["status"] == "frozen"
    assert payload["summary"]["frozen"] is True
    assert payload["summary"]["positive_count"] == 9
    assert payload["summary"]["new_non_adrb2_positive_count"] == 3
    assert payload["summary"]["distinct_positive_gpcr_target_count"] == 2
    assert payload["summary"]["leakage_audit_pass"] is True
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["accepted_candidate_rows"][0]["target"] == "DRD2_GPCR_BLIND"


def test_leakage_audit_failure_blocks_even_when_candidates_are_valid(tmp_path: Path) -> None:
    candidates = tmp_path / "config" / "candidates.csv"
    audit = tmp_path / "runs" / "audit.json"
    coverage = tmp_path / "runs" / "coverage.json"
    _write_csv(
        candidates,
        [
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_1"),
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_2"),
            _candidate("DRD2_GPCR_BLIND", "drd2_pos_3"),
        ],
    )
    _write_json(audit, _audit(False, key_overlap_count=1))
    _write_json(coverage, _coverage(6))

    payload = mod.build_packet(candidates_csv=candidates, leakage_audit_json=audit, positive_coverage_json=coverage)

    assert payload["summary"]["frozen"] is False
    assert "leakage_audit_not_green" in payload["summary"]["blockers"]
    assert "key_overlap_count" in payload["leakage_audit_gate"]["blockers"]


def test_adrb2_or_uncurated_rows_do_not_count_as_new_non_adrb2_positive(tmp_path: Path) -> None:
    candidates = tmp_path / "config" / "candidates.csv"
    audit = tmp_path / "runs" / "audit.json"
    coverage = tmp_path / "runs" / "coverage.json"
    bad = _candidate("ADRB2_GPCR_BLIND", "adrb2_extra")
    uncurated = _candidate("DRD2_GPCR_BLIND", "drd2_uncurated")
    uncurated["curation_status"] = "draft"
    _write_csv(candidates, [bad, uncurated])
    _write_json(audit, _audit(True))
    _write_json(coverage, _coverage(8))

    payload = mod.build_packet(candidates_csv=candidates, leakage_audit_json=audit, positive_coverage_json=coverage)

    assert payload["summary"]["frozen"] is False
    assert payload["summary"]["new_non_adrb2_positive_count"] == 0
    assert "candidate_rows_have_risk_flags" in payload["summary"]["blockers"]
    risks = [flag for row in payload["candidate_rows"] for flag in row["risk_flags"]]
    assert "adrb2_target_not_allowed_for_new_positive" in risks
    assert "curation_status_not_freeze_ready" in risks


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    candidates = tmp_path / "config" / "candidates.csv"
    audit = tmp_path / "runs" / "audit.json"
    coverage = tmp_path / "runs" / "coverage.json"
    out_json = tmp_path / "runs" / "freeze.json"
    out_md = tmp_path / "runs" / "freeze.md"
    _write_csv(candidates, [_candidate("DRD2_GPCR_BLIND", "drd2_pos_1")])
    _write_json(audit, _audit(True))
    _write_json(coverage, _coverage(6))

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_positive_coverage_freeze_packet.py"),
            "--candidates-csv",
            str(candidates),
            "--leakage-audit-json",
            str(audit),
            "--positive-coverage-json",
            str(coverage),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert payload["packet_type"] == "gpcr_positive_coverage_freeze_packet"
    assert "GPCR Positive Coverage Freeze Packet" in markdown
    assert "claim_promotion_allowed" in markdown
