import csv
import json
from pathlib import Path

from tools import build_casp17_protein_complex_massivefold_self_assessment_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path, target_id: str, base_dir: Path) -> None:
    rows = []
    for rank in range(1, 6):
        model_dir = base_dir / target_id.lower() / f"model_{rank}"
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
                "filename": f"{target_id}_model_{rank}.pdb",
                "rerank_bucket": "afm_basic_v3" if rank == 1 else "afm_dropout_full_v3",
                "confidence_score": str(105 - rank),
                "diversity_to_model1_rmsd": str(0 if rank == 1 else 5 * rank),
                "nearest_top5_rmsd": str(rank),
                "geometry_outlier_score": str(rank / 10),
                "low_conf_atom_fraction": str(rank / 100),
                "high_conf_atom_fraction": str(0.99 - rank / 100),
                "model1_candidate": "True" if rank == 1 else "False",
                "top5_candidate": "True",
                "top5_selection_rank": str(rank),
                "model_cif_path": str(model_cif),
                "viewer_html_path": str(viewer),
                "projection_svg_path": str(projection),
                "model_review_md_path": str(review),
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_builds_protein_complex_self_assessment_packet(tmp_path):
    h1311_manifest = tmp_path / "h1311_top5.csv"
    t2313_manifest = tmp_path / "t2313_top5.csv"
    _write_manifest(h1311_manifest, "H1311", tmp_path)
    _write_manifest(t2313_manifest, "T2313", tmp_path)
    coverage_json = tmp_path / "coverage.json"
    _write_json(
        coverage_json,
        {
            "rows": [
                {
                    "target_id": "H1311",
                    "coverage_status": "ready_review_only",
                    "top5_manifest_csv": str(h1311_manifest),
                },
                {
                    "target_id": "T2313",
                    "coverage_status": "ready_review_only",
                    "top5_manifest_csv": str(t2313_manifest),
                },
            ]
        },
    )
    args = mod.parse_args(
        [
            "--coverage-json",
            str(coverage_json),
            "--out-dir",
            str(tmp_path / "self_assessment"),
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
    assert summary["protein_complex_massivefold_self_assessment_status"] == (
        "protein_complex_massivefold_self_assessment_ready_external_only"
    )
    assert summary["target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert summary["blocked_target_count"] == 0
    assert summary["heteromer_or_immune_complex_count"] == 1
    assert summary["candidate_count"] == 10
    assert summary["model1_input_count"] == 2
    assert summary["top5_input_count"] == 10
    assert summary["missing_artifact_count"] == 0
    assert summary["internal_prediction_policy"] == "do_not_mark_as_internal_prediction"

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["H1311"]["target_family"] == "heteromer_or_immune_complex"
    assert rows["T2313"]["target_family"] == "protein_monomer_or_homomer_pool"
    assert rows["H1311"]["confidence_gap"] == "1"
    assert rows["H1311"]["top5_score_spread"] == "4"
    assert rows["H1311"]["mean_diversity_to_model1_rmsd"] == "17.5"
    assert (tmp_path / "self_assessment" / "h1311" / "self_assessment_candidates.csv").exists()
    assert (tmp_path / "self_assessment" / "t2313" / "SELF_ASSESSMENT.md").exists()


def test_marks_partial_when_manifest_is_missing(tmp_path):
    coverage_json = tmp_path / "coverage.json"
    _write_json(
        coverage_json,
        {
            "rows": [
                {
                    "target_id": "H1311",
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
            str(tmp_path / "self_assessment"),
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
    assert summary["protein_complex_massivefold_self_assessment_status"] == (
        "protein_complex_massivefold_self_assessment_partial"
    )
    assert summary["ready_target_count"] == 0
    assert summary["blocked_target_count"] == 1
    assert summary["first_blocked_target_id"] == "H1311"
    assert "top5_manifest_missing" in summary["first_blocker"]
    assert "top5_input_count_not_5" in summary["first_blocker"]
    assert "model1_input_count_not_1" in summary["first_blocker"]
