import json
from pathlib import Path

from tools import build_casp17_massivefold_freeze_ready_review_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return str(path)


def test_freeze_ready_review_packet_links_ready_viewers(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    ledger_json = tmp_path / "ledger.json"
    rerank_json = tmp_path / "rerank_{target_lower}.json"
    model = _touch(tmp_path / "r2350" / "model.cif")
    viewer = _touch(tmp_path / "r2350" / "viewer.html")
    projection = _touch(tmp_path / "r2350" / "projection.svg")
    top5_manifest = _touch(tmp_path / "r2350" / "top5_manifest.csv")
    _write_json(
        overlay_json,
        {
            "summary": {
                "massivefold_model1_combined_selector_overlay_status": (
                    "massivefold_model1_combined_selector_overlay_ready_external_only"
                )
            },
            "rows": [
                {
                    "target_id": "R2350",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "baseline_calibrated_freeze_ready",
                    "overlay_action": "carry_model1_as_external_only_freeze_ready",
                    "selected_model_filename": "model1.cif",
                    "probe_margin": "0.75",
                    "baseline_capture_rate": "0.500",
                },
                {
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "selector_blocked_manual_review",
                },
            ],
        },
    )
    _write_json(
        ledger_json,
        {
            "summary": {"massivefold_model_selection_ledger_status": "massivefold_model_selection_ledger_ready"},
            "rows": [
                {
                    "target_id": "R2350",
                    "selected_model_filename": "model1.cif",
                    "source_candidate_manifest_csv": top5_manifest,
                }
            ],
        },
    )
    _write_json(
        tmp_path / "rerank_r2350.json",
        {
            "summary": {
                "top5_manifest_csv": top5_manifest,
                "model1_confidence_score": "88.1",
            },
            "rows": [
                {
                    "target_id": "R2350",
                    "filename": "model1.cif",
                    "model1_candidate": True,
                    "top5_candidate": True,
                    "top5_selection_rank": "1",
                    "confidence_score": "88.1",
                    "model_cif_path": model,
                    "viewer_html_path": viewer,
                    "projection_svg_path": projection,
                },
                {
                    "target_id": "R2350",
                    "filename": "alt.cif",
                    "top5_candidate": True,
                    "top5_selection_rank": "2",
                    "confidence_score": "87.0",
                    "viewer_html_path": viewer,
                    "projection_svg_path": projection,
                },
                {"target_id": "R2350", "filename": "alt2.cif", "top5_candidate": True},
                {"target_id": "R2350", "filename": "alt3.cif", "top5_candidate": True},
                {"target_id": "R2350", "filename": "alt4.cif", "top5_candidate": True},
            ],
        },
    )
    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--model-selection-ledger-json",
            str(ledger_json),
            "--rerank-json-pattern",
            str(rerank_json),
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

    assert summary["massivefold_freeze_ready_review_packet_status"] == (
        "massivefold_freeze_ready_review_packet_ready_external_only"
    )
    assert summary["freeze_ready_target_count"] == 1
    assert summary["ready_review_count"] == 1
    assert summary["blocked_review_count"] == 0
    assert summary["model_present_count"] == 1
    assert summary["viewer_present_count"] == 1
    assert summary["projection_present_count"] == 1
    assert summary["top5_manifest_present_count"] == 1
    assert summary["top5_candidate_total"] == 5
    assert rows[0]["target_id"] == "R2350"
    assert rows[0]["review_status"] == "freeze_ready_review_ready_external_only"
    assert rows[0]["blockers"] == ""

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_rna_hybrid_r2350" / "FREEZE_READY_REVIEW.md").is_file()


def test_freeze_ready_review_packet_blocks_missing_selected_artifacts(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    ledger_json = tmp_path / "ledger.json"
    _write_json(
        overlay_json,
        {
            "rows": [
                {
                    "target_id": "R2350",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "baseline_calibrated_freeze_ready",
                    "selected_model_filename": "missing.cif",
                }
            ]
        },
    )
    _write_json(ledger_json, {"rows": [{"target_id": "R2350"}]})
    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--model-selection-ledger-json",
            str(ledger_json),
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

    assert payload["summary"]["massivefold_freeze_ready_review_packet_status"] == (
        "massivefold_freeze_ready_review_packet_blocked"
    )
    assert payload["summary"]["blocked_review_count"] == 1
    assert "model_file_missing" in payload["rows"][0]["blockers"]
    assert "top5_candidate_count_below_5" in payload["rows"][0]["blockers"]
