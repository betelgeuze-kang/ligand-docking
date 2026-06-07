import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_rna_self_assessment_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_source_manifest(path: Path, target_id: str) -> None:
    rows = []
    for rank in range(1, 6):
        rows.append(
            {
                "filename": f"{target_id}_model_{rank}.cif",
                "diversity_to_model1_rmsd": str(0 if rank == 1 else 10 + rank),
                "nearest_top5_rmsd": str(5 + rank),
                "geometry_outlier_score": str(rank / 10),
                "low_conf_atom_fraction": str(rank / 100),
                "high_conf_atom_fraction": str(0.5 - rank / 100),
            }
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _input_rows(target_id: str, manifest: Path, guard: str = "") -> list[dict]:
    rows = []
    for rank in range(1, 6):
        rows.append(
            {
                "target_id": target_id,
                "input_rank": rank,
                "input_role": "model1" if rank == 1 else "top5_decoy",
                "filename": f"{target_id}_model_{rank}.cif",
                "rerank_bucket": "basic" if rank == 1 else "alt",
                "confidence_score": str(61 - rank),
                "viewer_html_path": f"casp17/{target_id}/viewer_{rank}.html",
                "model_review_md_path": f"casp17/{target_id}/MODEL_REVIEW_{rank}.md",
                "sequence_guard": guard,
                "source_top5_manifest_csv": str(manifest),
            }
        )
    return rows


def test_builds_external_only_self_assessment_features(tmp_path):
    r2341_manifest = tmp_path / "r2341_top5.csv"
    r2345_manifest = tmp_path / "r2345_top5.csv"
    _write_source_manifest(r2341_manifest, "R2341")
    _write_source_manifest(r2345_manifest, "R2345")
    guard = "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    input_json = tmp_path / "input_packet.json"
    _write_json(
        input_json,
        {
            "rows": [
                {
                    "target_id": "R2341",
                    "input_status": "ready_external_model_selection_input",
                    "missing_artifact_count": 0,
                },
                {
                    "target_id": "R2345",
                    "input_status": "ready_external_model_selection_input",
                    "missing_artifact_count": 0,
                    "sequence_guard": guard,
                },
            ],
            "input_rows": [
                *_input_rows("R2341", r2341_manifest),
                *_input_rows("R2345", r2345_manifest, guard=guard),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--input-packet-json",
            str(input_json),
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
    assert summary["massivefold_rna_self_assessment_status"] == (
        "massivefold_rna_self_assessment_ready_external_only"
    )
    assert summary["target_count"] == 2
    assert summary["ready_target_count"] == 2
    assert summary["blocked_target_count"] == 0
    assert summary["candidate_count"] == 10
    assert summary["model1_input_count"] == 2
    assert summary["top5_input_count"] == 10
    assert summary["r2345_sequence_guard"] == guard
    assert summary["internal_prediction_policy"] == "do_not_mark_as_internal_prediction"
    assert summary["native_policy"] == "no_native_structure_or_post_release_accuracy_claim"

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["R2341"]["confidence_gap"] == "1"
    assert rows["R2341"]["top5_score_spread"] == "4"
    assert rows["R2341"]["mean_diversity_to_model1_rmsd"] == "13.5"
    assert rows["R2345"]["r2345_sequence_guard"] == guard
    assert (tmp_path / "self_assessment" / "r2341" / "self_assessment_candidates.csv").exists()
    assert (tmp_path / "self_assessment" / "r2345" / "SELF_ASSESSMENT.md").exists()


def test_blocks_r2345_when_guard_is_missing(tmp_path):
    manifest = tmp_path / "r2345_top5.csv"
    _write_source_manifest(manifest, "R2345")
    input_json = tmp_path / "input_packet.json"
    _write_json(
        input_json,
        {
            "rows": [
                {
                    "target_id": "R2345",
                    "input_status": "ready_external_model_selection_input",
                    "missing_artifact_count": 0,
                    "sequence_guard": "",
                }
            ],
            "input_rows": _input_rows("R2345", manifest),
        },
    )
    args = mod.parse_args(
        [
            "--input-packet-json",
            str(input_json),
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
    assert summary["massivefold_rna_self_assessment_status"] == "massivefold_rna_self_assessment_partial"
    assert summary["ready_target_count"] == 0
    assert summary["blocked_target_count"] == 1
    assert summary["first_blocked_target_id"] == "R2345"
    assert "r2345_sequence_guard_missing" in summary["first_blocker"]
