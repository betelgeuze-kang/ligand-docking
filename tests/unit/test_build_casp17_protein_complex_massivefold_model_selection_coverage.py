import json
from pathlib import Path

from tools.casp17 import build_casp17_protein_complex_massivefold_model_selection_coverage as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_target_artifacts(base: Path, target_id: str, protocol: str = "afm_basic_v3") -> dict[str, str]:
    suffix = target_id.lower()
    index_json = base / f"{suffix}_index.json"
    viewer_json = base / f"{suffix}_viewer.json"
    rerank_json = base / f"{suffix}_rerank.json"
    _write_json(
        index_json,
        {
            "summary": {
                "massivefold_model_pool_index_status": "massivefold_model_pool_representatives_extracted",
                "model_count": 14070,
                "selected_extract_count": 130,
                "selected_extracted_count": 130,
            }
        },
    )
    _write_json(
        viewer_json,
        {
            "summary": {
                "massivefold_representative_viewer_status": "massivefold_representative_viewers_ready",
                "viewer_ready_count": 130,
            }
        },
    )
    _write_json(
        rerank_json,
        {
            "summary": {
                "massivefold_representative_rerank_status": (
                    "massivefold_representative_rerank_ready_review_only"
                ),
                "model1_candidate_count": 1,
                "top5_candidate_count": 5,
                "model1_filename": f"{target_id}_model1.pdb",
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


def test_builds_ready_review_only_protein_complex_model_selection_coverage(tmp_path, monkeypatch):
    acquisition_json = tmp_path / "protein_acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "primary_target_id": "H1311",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "T2313",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
            ]
        },
    )
    artifacts = {
        "H1311": _write_target_artifacts(tmp_path, "H1311", protocol="afm_basic_v3"),
        "T2313": _write_target_artifacts(tmp_path, "T2313", protocol="afm_woTemplates_v3"),
    }
    monkeypatch.setattr(mod, "_target_artifacts", lambda target_id: artifacts[target_id])

    args = mod.parse_args(
        [
            "--acquisition-json",
            str(acquisition_json),
            "--target-ids",
            "H1311,T2313",
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
    assert summary["protein_complex_massivefold_model_selection_coverage_status"] == (
        "protein_complex_massivefold_model_selection_coverage_ready_review_only"
    )
    assert summary["target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert summary["partial_target_count"] == 0
    assert summary["verified_acquisition_count"] == 2
    assert summary["representative_extracted_target_count"] == 2
    assert summary["viewer_ready_target_count"] == 2
    assert summary["rerank_ready_target_count"] == 2
    assert summary["selected_model_count"] == 260
    assert summary["extracted_model_count"] == 260
    assert summary["viewer_ready_model_count"] == 260
    assert summary["top5_candidate_count"] == 10
    assert summary["model1_candidate_count"] == 2
    assert payload["rows"][1]["model1_protocol"] == "afm_woTemplates_v3"
    coverage_md = (tmp_path / "coverage.md").read_text(encoding="utf-8")
    assert "CASP17 Protein/Complex MassiveFold Model-Selection Coverage" in coverage_md
    assert "`H1311`" in coverage_md
    assert "`T2313`" in coverage_md


def test_marks_partial_when_protein_complex_artifacts_or_acquisition_are_missing(tmp_path, monkeypatch):
    acquisition_json = tmp_path / "protein_acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "primary_target_id": "H1311",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                },
                {
                    "primary_target_id": "H2321",
                    "pool_verification_status": "open_tarball_download_required",
                },
            ]
        },
    )
    artifacts = {
        "H1311": _write_target_artifacts(tmp_path, "H1311"),
        "H2321": {
            "index_json": str(tmp_path / "missing_index.json"),
            "viewer_json": str(tmp_path / "missing_viewer.json"),
            "rerank_json": str(tmp_path / "missing_rerank.json"),
        },
    }
    monkeypatch.setattr(mod, "_target_artifacts", lambda target_id: artifacts[target_id])

    args = mod.parse_args(
        [
            "--acquisition-json",
            str(acquisition_json),
            "--target-ids",
            "H1311,H2321",
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
    assert summary["protein_complex_massivefold_model_selection_coverage_status"] == (
        "protein_complex_massivefold_model_selection_coverage_partial"
    )
    assert summary["ready_target_count"] == 1
    assert summary["partial_target_count"] == 1
    assert summary["first_partial_target_id"] == "H2321"
    row_by_target = {row["target_id"]: row for row in payload["rows"]}
    assert row_by_target["H2321"]["coverage_status"] == "blocked_or_partial"
    assert row_by_target["H2321"]["blockers"] == (
        "acquisition_not_verified,representatives_not_extracted,viewers_not_ready,rerank_not_ready"
    )
