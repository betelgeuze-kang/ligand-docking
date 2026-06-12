from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import apply_refine_tier_public_benchmark_work_order as mod
from tools.product import build_refine_tier_public_benchmark_readiness as readiness


def _write_work_order(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=readiness.WORK_ORDER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _valid_work_order_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    proxy = [-9.0, -8.5, -8.0, -7.5, -7.0, -6.5, -6.0, -5.5]
    exp = [-10.0, -9.3, -8.7, -8.1, -7.2, -6.9, -6.1, -5.4]
    for idx, (pred, ref) in enumerate(zip(proxy, exp, strict=True)):
        split = "fit" if idx < 5 else "holdout"
        rows.append(
            {
                "work_order_id": f"refine_tier_public_benchmark_fill_{idx + 1:03d}",
                "target_input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
                "template_row_index": idx + 1,
                "benchmark_id": f"curated_{idx:03d}",
                "target_id": f"T{idx:03d}",
                "benchmark_family": "pdbbind_or_casf_refine_tier_public",
                "split": split,
                "provenance_kind": "operator_curated_public",
                "provenance_id": f"PDB:{idx:04d}",
                "license_ok": "true",
                "external_engine_calls": 0,
                "pose_rmsd_A": 1.2,
                "dockq": 0.65,
                "lddt_pli": 0.82,
                "deltaG_mm_gbsa_kcal_mol": pred,
                "deltaG_experimental_kcal_mol": ref,
                "operator_action": "append_validated_public_benchmark_row",
                "acceptance_rule": "fixture",
                "external_state_mutated": False,
            }
        )
    return rows


def test_placeholder_work_order_blocks_without_writing_candidate(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    _write_work_order(work_order, readiness._build_operator_work_order_rows(
        input_csv="config/refine_tier_public_benchmark_intake_current.csv",
        existing_row_count=0,
        valid_row_count=0,
        pose_pass_count=0,
        free_energy_pair_count=0,
        fit_split_present=False,
        holdout_or_test_split_present=False,
        min_total_rows=8,
        min_pose_rows=5,
        min_free_energy_pairs=5,
    ))

    payload = mod.apply_refine_tier_public_benchmark_work_order(work_order_csv=work_order, out_csv=candidate)
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_readiness_checked"] is False
    assert "blocked_work_order_rows_present" in summary["blockers"]
    assert "Fill or repair blocked work-order rows" in summary["next_required_step"]
    assert not candidate.exists()


def test_valid_work_order_writes_candidate_and_readiness_can_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    _write_work_order(work_order, _valid_work_order_rows())

    payload = mod.apply_refine_tier_public_benchmark_work_order(work_order_csv=work_order, out_csv=candidate)
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_work_order_apply_ready"
    assert summary["apply_ready"] is True
    assert summary["candidate_intake_written"] is True
    assert summary["candidate_readiness_checked"] is True
    assert summary["candidate_claim_grade_public_benchmark_ready"] is True
    assert summary["valid_intake_row_count"] == 8
    assert summary["write_intake_command"].endswith(
        "--write-intake --approval-token APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    )
    assert summary["approval_token_required"] == ""
    assert summary["approval_token_accepted"] is False
    assert "Review the candidate intake CSV" in summary["next_required_step"]
    assert candidate.read_text(encoding="utf-8").startswith("benchmark_id,target_id,")

    ready = readiness.build_refine_tier_public_benchmark_readiness(input_csv=candidate)
    assert ready["summary"]["claim_grade_public_benchmark_ready"] is True


def test_row_valid_but_aggregate_readiness_blocks_candidate(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    _write_work_order(work_order, _valid_work_order_rows()[:5])

    payload = mod.apply_refine_tier_public_benchmark_work_order(work_order_csv=work_order, out_csv=candidate)
    summary = payload["summary"]

    assert summary["apply_ready"] is False
    assert summary["candidate_intake_written"] is False
    assert summary["candidate_claim_grade_public_benchmark_ready"] is False
    assert "candidate_readiness_gate_not_ready" in summary["blockers"]
    assert "insufficient_total_rows" in summary["candidate_readiness_blockers"]
    assert "aggregate readiness gate" in summary["next_required_step"]
    assert not candidate.exists()


def test_write_intake_requires_all_rows_to_pass(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    rows = _valid_work_order_rows()
    rows[0]["external_engine_calls"] = 1
    _write_work_order(work_order, rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        write_intake=True,
    )

    assert payload["summary"]["intake_written"] is False
    assert "write_intake_blocked_until_work_order_rows_pass" in payload["summary"]["blockers"]
    assert "write_intake_approval_token_missing_or_invalid" in payload["summary"]["blockers"]
    assert "Fill or repair blocked work-order rows" in payload["summary"]["next_required_step"]
    assert not target.exists()


def test_write_intake_requires_approval_token_even_when_candidate_ready(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    rows = _valid_work_order_rows()
    for row in rows:
        row["target_input_csv"] = str(target)
    _write_work_order(work_order, rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        write_intake=True,
    )
    summary = payload["summary"]

    assert summary["apply_ready"] is False
    assert summary["candidate_readiness_checked"] is True
    assert summary["candidate_claim_grade_public_benchmark_ready"] is True
    assert summary["approval_token_required"] == "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE"
    assert summary["approval_token_present"] is False
    assert summary["approval_token_accepted"] is False
    assert "write_intake_approval_token_missing_or_invalid" in summary["blockers"]
    assert "required approval token" in summary["next_required_step"]
    assert not target.exists()


def test_write_intake_with_approval_token_writes_target_intake(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    target = tmp_path / "intake.csv"
    rows = _valid_work_order_rows()
    for row in rows:
        row["target_input_csv"] = str(target)
    _write_work_order(work_order, rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(
        work_order_csv=work_order,
        target_intake_csv=target,
        write_intake=True,
        approval_token="APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_INTAKE",
    )
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_intake_written"
    assert summary["apply_ready"] is True
    assert summary["approval_token_present"] is True
    assert summary["approval_token_accepted"] is True
    assert summary["intake_written"] is True
    assert target.read_text(encoding="utf-8").startswith("benchmark_id,target_id,")


def test_apply_blocks_wrong_target_action_mutation_and_duplicate_ids(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    candidate = tmp_path / "candidate.csv"
    rows = _valid_work_order_rows()
    rows[0]["target_input_csv"] = "config/other_intake.csv"
    rows[1]["operator_action"] = "manual_copy_without_validation"
    rows[2]["external_state_mutated"] = "true"
    rows[3]["benchmark_id"] = rows[4]["benchmark_id"]
    _write_work_order(work_order, rows)

    payload = mod.apply_refine_tier_public_benchmark_work_order(work_order_csv=work_order, out_csv=candidate)
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert payload["summary"]["apply_ready"] is False
    assert payload["summary"]["duplicate_benchmark_id_count"] == 1
    assert payload["summary"]["candidate_readiness_checked"] is False
    assert "target_input_csv_mismatch" in row_blockers
    assert "operator_action_unaccepted" in row_blockers
    assert "external_state_mutation_declared" in row_blockers
    assert "duplicate_benchmark_id" in row_blockers
    assert not candidate.exists()


def test_cli_writes_json_candidate_and_markdown(tmp_path: Path) -> None:
    work_order = tmp_path / "work_order.csv"
    out_json = tmp_path / "apply.json"
    candidate = tmp_path / "candidate.csv"
    out_md = tmp_path / "apply.md"
    _write_work_order(work_order, _valid_work_order_rows())

    mod.main(
        [
            "--work-order-csv",
            str(work_order),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(candidate),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["apply_ready"] is True
    assert payload["summary"]["candidate_readiness_checked"] is True
    assert candidate.exists()
    assert "Refine Tier Public Benchmark Work Order Apply" in out_md.read_text(encoding="utf-8")
    assert "candidate_readiness_status" in out_md.read_text(encoding="utf-8")
