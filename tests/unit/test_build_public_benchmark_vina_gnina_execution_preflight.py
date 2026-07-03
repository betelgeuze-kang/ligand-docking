from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_vina_gnina_execution_preflight as mod
from tools.product.build_public_benchmark_vina_gnina_comparison_work_order import APPROVAL_TOKEN


FIELDS = [
    "pose_id",
    "complex_id",
    "vina_score",
    "gnina_score",
    "comparison_score_source",
    "comparison_score_artifact_path",
    "comparison_score_artifact_sha256",
    "operator_engine_versions",
    "operator_prep_policy_sha256",
    "operator_method",
    "operator_reviewed_at_utc",
    "operator_id",
    "license_ok",
    "approval_token",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_results(path: Path) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "pdbbind_casf_pose_affinity_results_ready",
                "subset_identity": {
                    "artifact_rows": [
                        {
                            "name": "1abc_001",
                            "relative_path": "data_5_sdf/1abc_001",
                            "role": "pose",
                            "sha256": "a" * 64,
                        },
                        {
                            "name": "2def_002",
                            "relative_path": "data_5_sdf/2def_002",
                            "role": "pose",
                            "sha256": "b" * 64,
                        },
                    ]
                },
            }
        },
    )


def _write_work_order(path: Path, *, ready: bool = True) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": (
                    "public_benchmark_vina_gnina_comparison_work_order_ready"
                    if ready
                    else "blocked_public_benchmark_vina_gnina_comparison_work_order"
                ),
                "work_order_ready": ready,
                "pose_row_count": 2,
                "score_template_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
                "adapter_command_after_fill": (
                    "python3 tools/build_pdbbind_casf_pose_affinity_results.py "
                    "--comparison-scores-csv runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
            }
        },
    )


def _template_row(pose_id: str) -> dict[str, str]:
    return {
        "pose_id": pose_id,
        "complex_id": pose_id.split("_", 1)[0],
        "vina_score": "",
        "gnina_score": "",
        "comparison_score_source": "OPERATOR_FILL_SAME_INPUT_VINA_GNINA_SCORE_SOURCE",
        "comparison_score_artifact_path": "OPERATOR_FILL_LOCAL_SCORE_ARTIFACT",
        "comparison_score_artifact_sha256": "OPERATOR_FILL_LOCAL_SCORE_ARTIFACT_SHA256",
        "operator_engine_versions": "OPERATOR_FILL_VINA_AND_GNINA_VERSIONS",
        "operator_prep_policy_sha256": "OPERATOR_FILL_SHARED_PREP_POLICY_SHA256",
        "operator_method": "OPERATOR_FILL_METHOD",
        "operator_reviewed_at_utc": "",
        "operator_id": "",
        "license_ok": "",
        "approval_token": "",
    }


def _write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(_template_row("1abc_001"))
        writer.writerow(_template_row("2def_002"))


def _fake_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_execution_preflight_blocks_when_vina_gnina_binaries_missing(tmp_path: Path) -> None:
    results = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    _write_results(results)
    _write_work_order(work_order)
    _write_template(template)

    payload = mod.build_public_benchmark_vina_gnina_execution_preflight(
        results_json=results,
        work_order_json=work_order,
        score_template_csv=template,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_public_benchmark_vina_gnina_execution_preflight"
    assert summary["execution_preflight_ready"] is False
    assert summary["score_template_row_count"] == 2
    assert summary["ready_for_local_same_input_scoring_row_count"] == 0
    assert "vina_binary_missing" in summary["blockers"]
    assert "gnina_binary_missing" in summary["blockers"]
    assert summary["score_template_write_allowed"] is False
    assert summary["execution_enabled"] is False
    assert payload["rows"][0]["pose_artifact_path"] == "data_5_sdf/1abc_001"
    assert payload["rows"][0]["score_template_pending_fields"] == [
        "vina_score",
        "gnina_score",
        "comparison_score_source",
        "comparison_score_artifact_path",
        "comparison_score_artifact_sha256",
        "operator_engine_versions",
        "operator_prep_policy_sha256",
        "operator_method",
        "operator_reviewed_at_utc",
        "operator_id",
        "license_ok",
        "approval_token",
    ]


def test_execution_preflight_ready_with_explicit_local_engine_paths(tmp_path: Path) -> None:
    results = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    vina_bin = tmp_path / "bin/vina"
    gnina_bin = tmp_path / "bin/gnina"
    _write_results(results)
    _write_work_order(work_order)
    _write_template(template)
    _fake_executable(vina_bin)
    _fake_executable(gnina_bin)

    payload = mod.build_public_benchmark_vina_gnina_execution_preflight(
        results_json=results,
        work_order_json=work_order,
        score_template_csv=template,
        vina_bin=vina_bin,
        gnina_bin=gnina_bin,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "public_benchmark_vina_gnina_execution_preflight_ready"
    assert summary["execution_preflight_ready"] is True
    assert summary["ready_for_local_same_input_scoring_row_count"] == 2
    assert summary["blocked_for_local_same_input_scoring_row_count"] == 0
    assert summary["vina_binary_present"] is True
    assert summary["gnina_binary_present"] is True
    assert summary["approval_token_required"] == APPROVAL_TOKEN
    assert payload["rows"][0]["ready_for_local_same_input_scoring"] is True
    assert payload["rows"][0]["claim_promotion_allowed"] is False


def test_execution_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    results = tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json"
    work_order = tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json"
    template = tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    out_json = tmp_path / "runs/preflight.json"
    out_csv = tmp_path / "runs/preflight.csv"
    out_md = tmp_path / "runs/preflight.md"
    _write_results(results)
    _write_work_order(work_order)
    _write_template(template)

    assert mod.main(
        [
            "--results-json",
            str(results),
            "--work-order-json",
            str(work_order),
            "--score-template-csv",
            str(template),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "public_benchmark_vina_gnina_execution_preflight"
    assert out_csv.read_text(encoding="utf-8").startswith("pose_id,complex_id,")
    assert "Public Benchmark Vina/GNINA Execution Preflight" in out_md.read_text(encoding="utf-8")
