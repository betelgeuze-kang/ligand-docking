import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_rna_model_selection_input_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(base: Path, target_id: str, protocol: str) -> Path:
    manifest = base / f"{target_id.lower()}_top5.csv"
    rows = []
    for rank in range(1, 6):
        model_dir = base / target_id.lower() / f"model_{rank}"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_cif = model_dir / "model.cif"
        viewer = model_dir / "viewer.html"
        projection = model_dir / "projection.svg"
        review = model_dir / "MODEL_REVIEW.md"
        model_cif.write_text("data_model\n#\n", encoding="utf-8")
        viewer.write_text("<!doctype html><title>viewer</title>\n", encoding="utf-8")
        projection.write_text("<svg></svg>\n", encoding="utf-8")
        review.write_text("# review\n", encoding="utf-8")
        rows.append(
            {
                "quality_rank": str(rank),
                "target_id": target_id,
                "filename": f"{target_id}_model_{rank}.cif",
                "rerank_bucket": protocol if rank == 1 else f"{protocol}_alt",
                "confidence_score": str(60 - rank),
                "model1_candidate": "True" if rank == 1 else "False",
                "top5_candidate": "True",
                "top5_selection_rank": str(rank),
                "model_cif_path": str(model_cif),
                "viewer_html_path": str(viewer),
                "projection_svg_path": str(projection),
                "model_review_md_path": str(review),
            }
        )
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def test_builds_external_only_rna_model_selection_inputs(tmp_path):
    r2341_manifest = _write_manifest(tmp_path, "R2341", "basic")
    r2345_manifest = _write_manifest(tmp_path, "R2345", "woUnpaired")
    coverage_json = tmp_path / "coverage.json"
    _write_json(
        coverage_json,
        {
            "rows": [
                {
                    "target_id": "R2341",
                    "coverage_status": "ready_review_only",
                    "top5_manifest_csv": str(r2341_manifest),
                },
                {
                    "target_id": "R2345",
                    "coverage_status": "ready_review_only",
                    "top5_manifest_csv": str(r2345_manifest),
                },
            ]
        },
    )
    out_dir = tmp_path / "inputs"
    args = mod.parse_args(
        [
            "--coverage-json",
            str(coverage_json),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_rna_model_selection_input_status"] == (
        "massivefold_rna_model_selection_input_packet_ready_external_only"
    )
    assert summary["target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert summary["blocked_target_count"] == 0
    assert summary["model1_input_count"] == 2
    assert summary["top5_input_count"] == 10
    assert summary["missing_artifact_count"] == 0
    assert summary["r2345_sequence_guard"] == (
        "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    )
    assert summary["internal_prediction_policy"] == "do_not_mark_as_internal_prediction"
    assert summary["submission_policy"] == "do_not_submit_without_rule_check_and_operator_approval"

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["R2345"]["sequence_guard"] == (
        "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    )
    assert rows["R2341"]["model1_protocol"] == "basic"
    assert rows["R2345"]["model1_protocol"] == "woUnpaired"
    assert (out_dir / "r2341" / "input_manifest.csv").exists()
    assert (out_dir / "r2345" / "MODEL_SELECTION_INPUT.md").exists()
    assert (tmp_path / "PACKET.md").read_text(encoding="utf-8").count("ready_external_model_selection_input") == 2


def test_marks_partial_when_top5_manifest_is_missing(tmp_path):
    coverage_json = tmp_path / "coverage.json"
    _write_json(
        coverage_json,
        {
            "rows": [
                {
                    "target_id": "R2345",
                    "coverage_status": "ready_review_only",
                    "top5_manifest_csv": str(tmp_path / "missing.csv"),
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--coverage-json",
            str(coverage_json),
            "--out-dir",
            str(tmp_path / "inputs"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )
    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["massivefold_rna_model_selection_input_status"] == (
        "massivefold_rna_model_selection_input_packet_partial"
    )
    assert summary["ready_target_count"] == 0
    assert summary["blocked_target_count"] == 1
    assert summary["first_blocked_target_id"] == "R2345"
    assert "top5_manifest_missing" in summary["first_blocker"]
    assert "top5_input_count_not_5" in summary["first_blocker"]
    assert "model1_input_count_not_1" in summary["first_blocker"]
