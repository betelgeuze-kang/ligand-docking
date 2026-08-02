from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_hbond_backmap_report as mod


def _write_scores_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target",
        "ligand_id",
        "onsps_backmap_claim_safe",
        "onsps_backmap_status",
        "onsps_backmap_source",
        "onsps_backmap_blocked_reason",
        "onsps_backmap_site_count",
        "onsps_backmap_mapped_site_count",
        "hbond_donor_site_count",
        "hbond_acceptor_site_count",
        "hbond_blocked_reason",
        "hbond_angle_pass_fraction",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_product_image_smoke_receipt(
    path: Path,
    *,
    runner_smoke_dir: Path,
    ready: bool = True,
    outside_workspace: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "product_image_smoke_ready" if ready else "blocked_product_image_smoke",
        "mode": "rocm-runtime" if ready else "build",
        "runner_smoke_dir": str(runner_smoke_dir),
        "runner_smoke_dir_outside_workspace": outside_workspace,
        "workspace_runner_smoke_dir_cleanup_ready": outside_workspace,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _claim_safe_row() -> dict[str, object]:
    return {
        "target": "ADRB2",
        "ligand_id": "LIG-1",
        "onsps_backmap_claim_safe": "True",
        "onsps_backmap_status": "ok",
        "onsps_backmap_source": "rdkit_etkdg",
        "onsps_backmap_blocked_reason": "",
        "onsps_backmap_site_count": 4,
        "onsps_backmap_mapped_site_count": 3,
        "hbond_donor_site_count": 2,
        "hbond_acceptor_site_count": 1,
        "hbond_blocked_reason": "",
        "hbond_angle_pass_fraction": 0.75,
    }


def _fallback_row() -> dict[str, object]:
    return {
        "target": "ADRB2",
        "ligand_id": "LIG-2",
        "onsps_backmap_claim_safe": "False",
        "onsps_backmap_status": "fallback",
        "onsps_backmap_source": "smiles_char_fallback",
        "onsps_backmap_blocked_reason": "onsps_fallback_not_claim_safe:rdkit_unavailable",
        "onsps_backmap_site_count": 0,
        "onsps_backmap_mapped_site_count": 0,
        "hbond_donor_site_count": 0,
        "hbond_acceptor_site_count": 0,
        "hbond_blocked_reason": "",
        "hbond_angle_pass_fraction": "",
    }


def test_builder_produces_claim_safe_rate(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    _write_scores_csv(scores_csv, [_claim_safe_row(), _fallback_row()])

    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)

    assert artifact["status"] == mod.STATUS_OK
    assert artifact["execution_enabled"] is False
    assert artifact["external_state_mutated"] is False
    summary = artifact["summary"]
    assert summary["candidate_count"] == 2
    assert summary["claim_safe_count"] == 1
    assert summary["evidence_only_count"] == 1
    assert summary["claim_safe_rate"] == 0.5
    assert summary["total_donor_sites"] == 2
    assert summary["total_acceptor_sites"] == 1
    # The fallback row's structured reason_code is aggregated.
    assert summary["evidence_only_reason_counts"]["onsps_fallback_not_claim_safe"] == 1


def test_builder_row_mapping(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    _write_scores_csv(scores_csv, [_claim_safe_row()])

    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)
    row = artifact["rows"][0]

    assert row["entry_id"] == "ADRB2::LIG-1"
    assert row["evidence_tier"] == "claim_safe"
    assert row["claim_safe"] is True
    assert row["mapped_site_count"] == 3
    assert row["donor_count"] == 2
    assert row["acceptor_count"] == 1
    assert row["mapping_source"] == "rdkit_etkdg"
    assert row["backmap_status"] == "ok"
    assert row["hbond_angle_score"] == 0.75


def test_builder_fail_closed_on_missing_csv(tmp_path: Path) -> None:
    artifact = mod.build_hbond_backmap_report_artifact(tmp_path / "nope.csv")
    assert artifact["status"] == mod.STATUS_BLOCKED_MISSING
    assert artifact["summary"]["claim_safe_rate"] == 0.0
    assert artifact["rows"] == []


def test_builder_resolves_scores_csv_from_product_image_smoke_receipt(tmp_path: Path) -> None:
    smoke_dir = tmp_path / "runner-temp" / "product_image_smoke_runner_artifacts"
    scores_csv = smoke_dir / "backmapping_scores.csv"
    receipt = tmp_path / "runs" / "product_image_smoke_receipt_current.json"
    _write_scores_csv(scores_csv, [_claim_safe_row(), _fallback_row()])
    _write_product_image_smoke_receipt(receipt, runner_smoke_dir=smoke_dir)

    artifact = mod.build_hbond_backmap_report_artifact_from_product_image_smoke_receipt(receipt)

    assert artifact["status"] == mod.STATUS_OK
    assert artifact["scores_csv"] == str(scores_csv)
    assert artifact["summary"]["candidate_count"] == 2


def test_builder_blocks_receipt_workspace_artifact_root(tmp_path: Path) -> None:
    workspace_smoke_dir = tmp_path / "runs" / "product_image_smoke_runner_artifacts"
    receipt = tmp_path / "runs" / "product_image_smoke_receipt_current.json"
    _write_product_image_smoke_receipt(
        receipt,
        runner_smoke_dir=workspace_smoke_dir,
        outside_workspace=False,
    )

    artifact = mod.build_hbond_backmap_report_artifact_from_product_image_smoke_receipt(receipt)

    assert artifact["status"] == mod.STATUS_BLOCKED_RECEIPT_WORKSPACE_ARTIFACT_ROOT
    assert "workspace artifact root" in artifact["detail"]


def test_builder_fail_closed_on_empty_csv(tmp_path: Path) -> None:
    scores_csv = tmp_path / "empty.csv"
    _write_scores_csv(scores_csv, [])
    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)
    assert artifact["status"] == mod.STATUS_BLOCKED_EMPTY


def test_builder_fail_closed_on_wrong_schema(tmp_path: Path) -> None:
    scores_csv = tmp_path / "wrong.csv"
    with scores_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target", "ligand_id", "score"])
        writer.writeheader()
        writer.writerow({"target": "ADRB2", "ligand_id": "LIG-1", "score": 0.5})
    artifact = mod.build_hbond_backmap_report_artifact(scores_csv)
    assert artifact["status"] == mod.STATUS_BLOCKED_SCHEMA


def test_main_writes_artifacts_and_returns_zero(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    _write_scores_csv(scores_csv, [_claim_safe_row(), _fallback_row()])
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"
    out_csv = tmp_path / "out.csv"

    rc = mod.main(
        [
            "--scores-csv",
            str(scores_csv),
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
    assert payload["status"] == mod.STATUS_OK
    assert out_md.read_text(encoding="utf-8").startswith("# H-Bond BackMap Candidate Report")
    csv_rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert len(csv_rows) == 2
    assert csv_rows[0]["entry_id"] == "ADRB2::LIG-1"


def test_main_returns_nonzero_when_blocked(tmp_path: Path) -> None:
    rc = mod.main(
        [
            "--scores-csv",
            str(tmp_path / "missing.csv"),
            "--out-json",
            str(tmp_path / "o.json"),
            "--out-md",
            str(tmp_path / "o.md"),
            "--out-csv",
            str(tmp_path / "o.csv"),
        ]
    )
    assert rc == 1
