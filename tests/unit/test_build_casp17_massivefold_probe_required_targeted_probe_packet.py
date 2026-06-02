import json
from pathlib import Path

from tools import build_casp17_massivefold_probe_required_targeted_probe_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return str(path)


def _top5_payload(
    *,
    target_id: str,
    model1_filename: str,
    model1_score: float,
    competitor_filename: str,
    competitor_score: float,
    manifest: str,
    root: Path,
) -> dict:
    model1_model = _touch(root / target_id.lower() / "model1.cif")
    model1_viewer = _touch(root / target_id.lower() / "model1.html")
    model1_projection = _touch(root / target_id.lower() / "model1.svg")
    competitor_model = _touch(root / target_id.lower() / "competitor.cif")
    competitor_viewer = _touch(root / target_id.lower() / "competitor.html")
    competitor_projection = _touch(root / target_id.lower() / "competitor.svg")
    rows = [
        {
            "target_id": target_id,
            "filename": model1_filename,
            "model1_candidate": True,
            "top5_candidate": True,
            "top5_selection_rank": 1,
            "confidence_score": model1_score,
            "geometry_outlier_score": 0,
            "low_conf_atom_fraction": 0,
            "diversity_to_model1_rmsd": 0,
            "model_cif_path": model1_model,
            "viewer_html_path": model1_viewer,
            "projection_svg_path": model1_projection,
        },
        {
            "target_id": target_id,
            "filename": competitor_filename,
            "model1_candidate": False,
            "top5_candidate": True,
            "top5_selection_rank": 2,
            "confidence_score": competitor_score,
            "geometry_outlier_score": 0,
            "low_conf_atom_fraction": 0,
            "diversity_to_model1_rmsd": 0,
            "model_cif_path": competitor_model,
            "viewer_html_path": competitor_viewer,
            "projection_svg_path": competitor_projection,
        },
    ]
    while len(rows) < 5:
        idx = len(rows) + 1
        rows.append(
            {
                "target_id": target_id,
                "filename": f"decoy_{idx}.cif",
                "top5_candidate": True,
                "top5_selection_rank": idx,
                "confidence_score": competitor_score - idx,
                "geometry_outlier_score": 0,
                "low_conf_atom_fraction": 0,
                "diversity_to_model1_rmsd": 0,
                "model_cif_path": competitor_model,
                "viewer_html_path": competitor_viewer,
                "projection_svg_path": competitor_projection,
            }
        )
    return {"summary": {"top5_manifest_csv": manifest}, "rows": rows}


def test_probe_required_targeted_probe_packet_classifies_clear_watch_and_fail(tmp_path: Path) -> None:
    hold_json = tmp_path / "hold.json"
    rerank_pattern = tmp_path / "rerank_{target_lower}.json"
    manifest = _touch(tmp_path / "top5.csv")
    _write_json(
        hold_json,
        {
            "summary": {
                "massivefold_hold_probe_review_packet_status": (
                    "massivefold_hold_probe_review_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "review_rank": 1,
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "review_class": "probe_required_review",
                    "primary_model_filename": "clear_model1.pdb",
                    "top5_manifest_csv": manifest,
                    "confidence_gap": "0.7",
                    "risk_score": "51",
                },
                {
                    "review_rank": 2,
                    "target_id": "R2341",
                    "target_group": "rna_hybrid",
                    "review_class": "probe_required_review",
                    "primary_model_filename": "watch_model1.cif",
                    "top5_manifest_csv": manifest,
                    "confidence_gap": "0.2",
                    "risk_score": "44",
                },
                {
                    "review_rank": 3,
                    "target_id": "H2321",
                    "target_group": "protein_complex",
                    "review_class": "probe_required_review",
                    "primary_model_filename": "fail_model1.pdb",
                    "top5_manifest_csv": manifest,
                    "confidence_gap": "0.1",
                    "risk_score": "42",
                },
                {
                    "review_rank": 4,
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "review_class": "manual_blocked_review",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "rerank_h1311.json",
        _top5_payload(
            target_id="H1311",
            model1_filename="clear_model1.pdb",
            model1_score=100.0,
            competitor_filename="clear_competitor.pdb",
            competitor_score=98.0,
            manifest=manifest,
            root=tmp_path,
        ),
    )
    _write_json(
        tmp_path / "rerank_r2341.json",
        _top5_payload(
            target_id="R2341",
            model1_filename="watch_model1.cif",
            model1_score=100.0,
            competitor_filename="watch_competitor.cif",
            competitor_score=99.8,
            manifest=manifest,
            root=tmp_path,
        ),
    )
    _write_json(
        tmp_path / "rerank_h2321.json",
        _top5_payload(
            target_id="H2321",
            model1_filename="fail_model1.pdb",
            model1_score=98.0,
            competitor_filename="fail_competitor.pdb",
            competitor_score=100.0,
            manifest=manifest,
            root=tmp_path,
        ),
    )
    args = mod.parse_args(
        [
            "--hold-probe-review-json",
            str(hold_json),
            "--rerank-json-pattern",
            str(rerank_pattern),
            "--out-dir",
            str(tmp_path / "packet"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
            "--out-html",
            str(tmp_path / "packet.html"),
        ]
    )

    payload = mod.build_payload(args)
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["massivefold_probe_required_targeted_probe_packet_status"] == (
        "massivefold_probe_required_targeted_probe_packet_ready_external_only"
    )
    assert summary["probe_target_count"] == 3
    assert summary["ready_probe_count"] == 3
    assert summary["probe_pass_count"] == 1
    assert summary["probe_watch_count"] == 1
    assert summary["probe_fail_count"] == 1
    assert summary["freeze_candidate_count"] == 1
    assert summary["watch_recommendation_count"] == 1
    assert summary["manual_review_recommendation_count"] == 1
    assert summary["top5_candidate_total"] == 15
    assert rows[0]["probe_result"] == "probe_pass_model1_retained_clear"
    assert rows[1]["probe_result"] == "probe_watch_model1_retained_low_margin"
    assert rows[2]["probe_result"] == "probe_fail_model1_displaced"

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_protein_complex_h1311" / "TARGETED_PROBE.md").is_file()


def test_probe_required_targeted_probe_packet_blocks_missing_rerank_artifacts(tmp_path: Path) -> None:
    hold_json = tmp_path / "hold.json"
    _write_json(
        hold_json,
        {
            "rows": [
                {
                    "review_rank": 1,
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "review_class": "probe_required_review",
                    "primary_model_filename": "missing.pdb",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--hold-probe-review-json",
            str(hold_json),
            "--rerank-json-pattern",
            str(tmp_path / "missing_{target_lower}.json"),
            "--out-dir",
            str(tmp_path / "packet"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
            "--out-html",
            str(tmp_path / "packet.html"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_probe_required_targeted_probe_packet_status"] == (
        "massivefold_probe_required_targeted_probe_packet_blocked"
    )
    assert payload["summary"]["blocked_probe_count"] == 1
    assert "primary_model_missing_from_rerank_rows" in payload["rows"][0]["blockers"]
    assert "top5_candidate_count_below_5" in payload["rows"][0]["blockers"]
