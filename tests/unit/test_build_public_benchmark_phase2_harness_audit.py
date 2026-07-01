from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_phase2_harness_audit as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _contract_payload(*, include_all_requirements: bool = True) -> dict[str, object]:
    requirement_ids = list(mod.REQUIREMENT_ORDER)
    if not include_all_requirements:
        requirement_ids.remove("posebusters_style_validity_checks")
    return {
        "summary": {
            "status": "product_public_benchmark_contract_ready",
            "phase2_public_benchmark_harness_ready": include_all_requirements,
            "phase2_ready_requirement_count": len(requirement_ids),
            "phase2_requirement_count": len(mod.REQUIREMENT_ORDER),
            "pdbbind_execution_summary_json": "runs/pdbbind_casf_pose_affinity_results_current.json",
            "pdbbind_pose_success_rate": 1.0,
            "pdbbind_pose_success_threshold": 0.35,
            "pdbbind_symmetry_aware_ligand_rmsd_coverage": 1.0,
            "pdbbind_posebusters_valid_rate": 1.0,
            "vina_gnina_comparison_adapter_status": "vina_gnina_comparison_adapter_not_requested",
            "vina_gnina_comparison_adapter_score_evidence_ready": False,
            "phase2_enrichment_ready_sources": "lit_pcba_virtual_screening;dude_z_decoy_smoke",
        },
        "phase2_requirements": [
            {
                "requirement_id": requirement_id,
                "status": "ready",
                "ready": True,
                "evidence": "runs/evidence.json",
                "blocker": "",
                "blockers": [],
            }
            for requirement_id in requirement_ids
        ],
    }


def test_phase2_audit_ready_even_when_vina_gnina_scores_not_requested(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    _write_json(contract, _contract_payload())

    payload = mod.build_public_benchmark_phase2_harness_audit(contract_json=contract)

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_phase2_harness_audit_ready"
    assert summary["phase2_harness_audit_ready"] is True
    assert summary["ready_requirement_count"] == 5
    assert summary["vina_gnina_comparison_adapter_ready"] is True
    assert summary["vina_gnina_comparison_adapter_score_evidence_ready"] is False
    assert summary["vina_gnina_comparison_score_evidence_required_for_phase2"] is False
    adapter = next(row for row in payload["rows"] if row["requirement_id"] == "vina_gnina_comparison_adapter")
    assert adapter["requirement_kind"] == "phase2_required_adapter_contract"
    assert "score_evidence_required_for_phase2=false" in adapter["notes"]
    assert adapter["execution_enabled"] is False


def test_phase2_audit_normalizes_semicolon_evidence_paths(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    payload = _contract_payload()
    enrichment = next(
        row for row in payload["phase2_requirements"] if row["requirement_id"] == "dude_or_lit_pcba_enrichment"
    )
    enrichment["evidence"] = (
        str(mod.ROOT / "runs/lit_pcba_scorecard_current.json")
        + ";"
        + str(mod.ROOT / "runs/dude_z_decoy_smoke_scorecard_current.json")
    )
    _write_json(contract, payload)

    audit = mod.build_public_benchmark_phase2_harness_audit(contract_json=contract)

    row = next(row for row in audit["rows"] if row["requirement_id"] == "dude_or_lit_pcba_enrichment")
    assert row["evidence"] == "runs/lit_pcba_scorecard_current.json;runs/dude_z_decoy_smoke_scorecard_current.json"


def test_phase2_audit_blocks_missing_requirement_row(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    _write_json(contract, _contract_payload(include_all_requirements=False))

    payload = mod.build_public_benchmark_phase2_harness_audit(contract_json=contract)

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_phase2_harness_audit"
    assert summary["phase2_harness_audit_ready"] is False
    assert "posebusters_style_validity_checks:phase2_requirement_row_missing" in summary["blockers"]
    row = next(row for row in payload["rows"] if row["requirement_id"] == "posebusters_style_validity_checks")
    assert row["status"] == "blocked"
    assert row["blocker"] == "phase2_requirement_row_missing"


def test_main_writes_phase2_audit_artifacts(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"
    _write_json(contract, _contract_payload())

    rc = mod.main(
        [
            "--contract-json",
            str(contract),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "public_benchmark_phase2_harness_audit_ready"
    assert out_md.read_text(encoding="utf-8").startswith("# Public Benchmark Phase 2 Harness Audit")
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["requirement_id"] for row in rows] == list(mod.REQUIREMENT_ORDER)
