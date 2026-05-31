import json
from pathlib import Path

from tools import build_casp17_massivefold_rna_model_selection_coverage as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_target_artifacts(base: Path, target_id: str, protocol: str = "basic") -> dict[str, str]:
    suffix = target_id.lower()
    index_json = base / f"{suffix}_index.json"
    viewer_json = base / f"{suffix}_viewer.json"
    rerank_json = base / f"{suffix}_rerank.json"
    _write_json(
        index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": "massivefold_model_pool_representatives_extracted",
                "model_count": 8040,
                "selected_extract_count": 40,
                "selected_extracted_count": 40,
            }
        },
    )
    _write_json(
        viewer_json,
        {
            "summary": {
                "massivefold_representative_viewer_status": "massivefold_representative_viewers_ready",
                "viewer_ready_count": 40,
            }
        },
    )
    _write_json(
        rerank_json,
        {
            "summary": {
                "massivefold_representative_rerank_status": "massivefold_representative_rerank_ready_review_only",
                "model1_candidate_count": 1,
                "top5_candidate_count": 5,
                "model1_filename": f"{target_id}_model1.cif",
                "model1_protocol": protocol,
                "top5_manifest_csv": f"casp17/massivefold_representative_rerank/{suffix}/top5_manifest.csv",
            }
        },
    )
    return {
        "index_json": str(index_json),
        "viewer_json": str(viewer_json),
        "rerank_json": str(rerank_json),
    }


def test_builds_ready_review_only_rna_model_selection_coverage(tmp_path, monkeypatch):
    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "primary_target_id": "R2341",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2345",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2350",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2351",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2352",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2353",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
            ]
        },
    )
    monkeypatch.setattr(
        mod,
        "TARGET_ARTIFACTS",
        {
            "R2341": _write_target_artifacts(tmp_path, "R2341", protocol="basic"),
            "R2345": _write_target_artifacts(tmp_path, "R2345", protocol="woUnpaired"),
            "R2350": _write_target_artifacts(tmp_path, "R2350", protocol="woPaired"),
            "R2351": _write_target_artifacts(tmp_path, "R2351", protocol="woTemplates"),
            "R2352": _write_target_artifacts(tmp_path, "R2352", protocol="woUnpaired"),
            "R2353": _write_target_artifacts(tmp_path, "R2353", protocol="woPaired"),
        },
    )

    args = mod.parse_args(
        [
            "--acquisition-json",
            str(acquisition_json),
            "--target-ids",
            "R2341,R2345,R2350,R2351,R2352,R2353",
            "--out-json",
            str(tmp_path / "coverage.json"),
            "--out-csv",
            str(tmp_path / "coverage.csv"),
            "--out-md",
            str(tmp_path / "coverage.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_rna_model_selection_coverage_status"] == (
        "massivefold_rna_model_selection_coverage_ready_review_only"
    )
    assert summary["target_count"] == 6
    assert summary["ready_target_count"] == 6
    assert summary["partial_target_count"] == 0
    assert summary["verified_acquisition_count"] == 6
    assert summary["representative_extracted_target_count"] == 6
    assert summary["viewer_ready_target_count"] == 6
    assert summary["rerank_ready_target_count"] == 6
    assert summary["selected_model_count"] == 240
    assert summary["extracted_model_count"] == 240
    assert summary["viewer_ready_model_count"] == 240
    assert summary["top5_candidate_count"] == 30
    assert summary["model1_candidate_count"] == 6
    assert payload["rows"][1]["model1_protocol"] == "woUnpaired"
    assert payload["rows"][2]["model1_protocol"] == "woPaired"
    assert payload["rows"][3]["model1_protocol"] == "woTemplates"
    assert payload["rows"][4]["model1_protocol"] == "woUnpaired"
    assert payload["rows"][5]["model1_protocol"] == "woPaired"
    assert (tmp_path / "coverage.csv").read_text(encoding="utf-8").count("\n") == 7
    coverage_md = (tmp_path / "coverage.md").read_text(encoding="utf-8")
    assert "`R2345`" in coverage_md
    assert "`R2350`" in coverage_md
    assert "`R2351`" in coverage_md
    assert "`R2352`" in coverage_md
    assert "`R2353`" in coverage_md


def test_marks_partial_when_target_artifacts_or_acquisition_are_missing(tmp_path, monkeypatch):
    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "primary_target_id": "R2341",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "R2345",
                    "pool_verification_status": "open_tarball_download_required",
                },
            ]
        },
    )
    monkeypatch.setattr(
        mod,
        "TARGET_ARTIFACTS",
        {
            "R2341": _write_target_artifacts(tmp_path, "R2341"),
            "R2345": {
                "index_json": str(tmp_path / "missing_index.json"),
                "viewer_json": str(tmp_path / "missing_viewer.json"),
                "rerank_json": str(tmp_path / "missing_rerank.json"),
            },
        },
    )

    args = mod.parse_args(
        [
            "--acquisition-json",
            str(acquisition_json),
            "--target-ids",
            "R2341,R2345",
            "--out-json",
            str(tmp_path / "coverage.json"),
            "--out-csv",
            str(tmp_path / "coverage.csv"),
            "--out-md",
            str(tmp_path / "coverage.md"),
        ]
    )
    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["massivefold_rna_model_selection_coverage_status"] == (
        "massivefold_rna_model_selection_coverage_partial"
    )
    assert summary["ready_target_count"] == 1
    assert summary["partial_target_count"] == 1
    assert summary["first_partial_target_id"] == "R2345"
    row_by_target = {row["target_id"]: row for row in payload["rows"]}
    assert row_by_target["R2345"]["coverage_status"] == "blocked_or_partial"
    assert row_by_target["R2345"]["blockers"] == (
        "acquisition_not_verified,representatives_not_extracted,viewers_not_ready,rerank_not_ready"
    )
