"""End-to-end shadow execution runner tests (P1-9, roadmap §17)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
)
from tools.product import run_docking_shadow_execution as mod

pytest.importorskip("rdkit")


def _receptor(path: Path, atom_count: int = 40) -> Path:
    path.write_text(
        "".join(
            "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
            % (index, index, float(index % 9), float(index % 5), float(index % 3))
            for index in range(1, atom_count + 1)
        ),
        encoding="utf-8",
    )
    return path


def _oracle_inputs(tmp_path: Path, *, license_ok: str = "true") -> tuple[Path, Path]:
    receipt = tmp_path / "oracle_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "baseline_engine": "vina",
                "engine_version": "1.2.5",
                "score_artifact_path": "runs/oracle/vina_case.log",
                "score_artifact_sha256": "a" * 64,
                "prep_policy_sha256": "b" * 64,
                "operator_id": "operator_1",
                "reviewed_at_utc": "2026-07-27T00:00:00Z",
                "license_ok": license_ok,
            }
        ),
        encoding="utf-8",
    )
    rows = tmp_path / "oracle_rows.csv"
    rows.write_text(
        "pose_id,rank,score,geometric_valid,chemistry_valid\n"
        "oracle_pose_1,1,-7.4,true,true\n"
        "oracle_pose_2,2,-6.9,true,true\n",
        encoding="utf-8",
    )
    return receipt, rows


def _run(tmp_path: Path, **overrides):
    kwargs = {
        "receptor_pdb": str(_receptor(tmp_path / "receptor.pdb")),
        "ligand_smiles": "CCCCCCO",
        "target_id": "T1",
        "ligand_id": "L1",
        "case_id": "case_1",
        "max_conformers": 6,
        "seed": 7,
    }
    kwargs.update(overrides)
    return mod.run_docking_shadow_execution(**kwargs)


def test_two_internal_surfaces_run_on_one_prepared_input(tmp_path: Path) -> None:
    summary = _run(tmp_path)["summary"]

    assert summary["status"] == mod.STATUS_READY
    assert summary["ready"] is True
    assert summary["engine_surfaces"] == [
        ENGINE_SURFACE_ENGINE_V2,
        ENGINE_SURFACE_LEGACY_PRODUCT,
    ]
    assert summary["prepared_input_hash"]
    assert summary["comparison_comparable"] is True
    assert summary["pairwise_delta_count"] == 1


def test_every_surface_reports_the_same_prepared_input_hash(tmp_path: Path) -> None:
    packet = _run(tmp_path)
    expected = packet["summary"]["prepared_input_hash"]

    results = packet["shadow_execution"]["results"]
    assert results
    for bundle in results.values():
        assert bundle["prepared_input_hashes"]["prepared_input_hash"] == expected


def test_legacy_stays_active_and_v2_stays_shadow_only(tmp_path: Path) -> None:
    record = _run(tmp_path)["shadow_execution"]

    assert record["active_engine_surface"] == ENGINE_SURFACE_LEGACY_PRODUCT
    assert record["shadow_result_surfaces"] == [ENGINE_SURFACE_ENGINE_V2]
    assert record["claim_promotion_allowed"] is False
    assert record["shadow_only_locked"] is True


def test_both_internal_surfaces_share_the_candidate_budget(tmp_path: Path) -> None:
    packet = _run(tmp_path, candidate_budget=5)

    budgets = {
        bundle["runtime_budget"]["candidate_budget"]
        for bundle in packet["shadow_execution"]["results"].values()
    }
    assert budgets == {5}
    assert packet["summary"]["candidate_budget"] == 5


def test_only_v2_reports_refinement(tmp_path: Path) -> None:
    results = _run(tmp_path)["shadow_execution"]["results"]

    legacy = results[ENGINE_SURFACE_LEGACY_PRODUCT]["evidence_receipts"]
    v2 = results[ENGINE_SURFACE_ENGINE_V2]["evidence_receipts"]
    assert legacy["refinement_run_count"] == 0
    assert v2["refinement_run_count"] >= 1


def test_oracle_inputs_produce_a_three_surface_record(tmp_path: Path) -> None:
    receipt, rows = _oracle_inputs(tmp_path)
    packet = _run(
        tmp_path,
        oracle_receipt_json=str(receipt),
        oracle_rows_csv=str(rows),
    )
    summary = packet["summary"]

    assert summary["ready"] is True
    assert summary["executed_surface_count"] == 3
    assert summary["pairwise_delta_count"] == 3
    assert ENGINE_SURFACE_EXTERNAL_ORACLE in summary["engine_surfaces"]
    assert summary["oracle_inputs_supplied"] is True


def test_oracle_is_recorded_without_being_executed(tmp_path: Path) -> None:
    receipt, rows = _oracle_inputs(tmp_path)
    packet = _run(
        tmp_path,
        oracle_receipt_json=str(receipt),
        oracle_rows_csv=str(rows),
    )

    assert packet["summary"]["baseline_executed_in_process"] is False
    oracle = packet["shadow_execution"]["results"][ENGINE_SURFACE_EXTERNAL_ORACLE]
    assert oracle["evidence_receipts"]["executed_in_process"] is False
    assert oracle["evidence_receipts"]["execution_locus"] == "offline_operator_host"


def test_unlicensed_oracle_blocks_the_run(tmp_path: Path) -> None:
    receipt, rows = _oracle_inputs(tmp_path, license_ok="false")
    summary = _run(
        tmp_path,
        oracle_receipt_json=str(receipt),
        oracle_rows_csv=str(rows),
    )["summary"]

    assert summary["ready"] is False
    assert "external_oracle:baseline_license_not_confirmed" in summary["blockers"]


def test_missing_receptor_blocks_before_preparation(tmp_path: Path) -> None:
    summary = _run(tmp_path, receptor_pdb=str(tmp_path / "absent.pdb"))["summary"]

    assert summary["status"] == mod.STATUS_BLOCKED
    assert summary["executed_surface_count"] == 0
    assert any(b.startswith("receptor_pdb_not_found") for b in summary["blockers"])


def test_missing_ligand_smiles_blocks_before_preparation(tmp_path: Path) -> None:
    summary = _run(tmp_path, ligand_smiles="")["summary"]

    assert "ligand_smiles_missing" in summary["blockers"]


def test_macrocycle_case_emits_counted_failures_not_a_gap(tmp_path: Path) -> None:
    packet = _run(tmp_path, ligand_smiles="C1CCCCCCCCCCCC1")
    summary = packet["summary"]

    assert summary["ready"] is False
    assert summary["prepared_packet_ready"] is False
    for bundle in packet["shadow_execution"]["results"].values():
        assert bundle["failure_denominator"]["failed_case_count"] == 1
        assert bundle["failure_denominator"]["accounted"] is True


def test_runner_declares_read_only_posture(tmp_path: Path) -> None:
    summary = _run(tmp_path)["summary"]

    for flag, expected in mod.READ_ONLY_FLAGS.items():
        assert summary[flag] == expected
    assert "does not run Vina" in summary["claim_boundary"]


def test_csv_rows_cover_every_surface_and_pose(tmp_path: Path) -> None:
    packet = _run(tmp_path)
    rows = packet["rows"]

    assert rows
    surfaces = {row["engine_surface"] for row in rows}
    assert surfaces == {ENGINE_SURFACE_LEGACY_PRODUCT, ENGINE_SURFACE_ENGINE_V2}
    active_rows = [row for row in rows if row["active_surface"]]
    assert active_rows
    assert all(row["engine_surface"] == ENGINE_SURFACE_LEGACY_PRODUCT for row in active_rows)


def test_main_writes_artifacts_and_exits_zero(tmp_path: Path) -> None:
    receptor = _receptor(tmp_path / "receptor.pdb")
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    code = mod.main(
        [
            "--receptor-pdb",
            str(receptor),
            "--ligand-smiles",
            "CCCCCCO",
            "--case-id",
            "case_1",
            "--max-conformers",
            "6",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--quiet",
        ]
    )

    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == mod.STATUS_READY
    assert payload["preparation_packet"]["ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("engine_surface,")
    assert "# Docking Shadow Execution" in out_md.read_text(encoding="utf-8")


def test_main_exits_nonzero_when_blocked(tmp_path: Path) -> None:
    code = mod.main(
        [
            "--receptor-pdb",
            str(tmp_path / "absent.pdb"),
            "--ligand-smiles",
            "CCCCCCO",
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            "",
            "--out-md",
            "",
            "--quiet",
        ]
    )

    assert code == 1
