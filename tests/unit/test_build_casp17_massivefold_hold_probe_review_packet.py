import json
from pathlib import Path

from tools import build_casp17_massivefold_hold_probe_review_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return str(path)


def _rerank_payload(
    target_id: str,
    primary_filename: str,
    primary_model: str,
    primary_viewer: str,
    primary_projection: str,
    top5_manifest: str,
    alternate_filename: str = "",
    alternate_model: str = "",
    alternate_viewer: str = "",
    alternate_projection: str = "",
) -> dict:
    rows = [
        {
            "target_id": target_id,
            "filename": primary_filename,
            "model1_candidate": True,
            "top5_candidate": True,
            "top5_selection_rank": "1",
            "confidence_score": "91.5",
            "model_cif_path": primary_model,
            "viewer_html_path": primary_viewer,
            "projection_svg_path": primary_projection,
        },
    ]
    if alternate_filename:
        rows.append(
            {
                "target_id": target_id,
                "filename": alternate_filename,
                "model1_candidate": False,
                "top5_candidate": True,
                "top5_selection_rank": "2",
                "confidence_score": "91.1",
                "model_cif_path": alternate_model,
                "viewer_html_path": alternate_viewer,
                "projection_svg_path": alternate_projection,
            }
        )
    while len([row for row in rows if row.get("top5_candidate")]) < 5:
        idx = len(rows) + 1
        rows.append(
            {
                "target_id": target_id,
                "filename": f"decoy_{idx}.cif",
                "top5_candidate": True,
                "top5_selection_rank": str(idx),
            }
        )
    return {"summary": {"top5_manifest_csv": top5_manifest}, "rows": rows}


def test_hold_probe_review_packet_links_manual_interface_and_probe_reviews(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    ledger_json = tmp_path / "ledger.json"
    freeze_json = tmp_path / "freeze.json"
    rerank_pattern = tmp_path / "rerank_{target_lower}.json"
    manifest = _touch(tmp_path / "top5_manifest.csv")

    manual_model = _touch(tmp_path / "r2352" / "primary.cif")
    manual_viewer = _touch(tmp_path / "r2352" / "viewer.html")
    manual_projection = _touch(tmp_path / "r2352" / "projection.svg")
    manual_alt_model = _touch(tmp_path / "r2352" / "alt.cif")
    manual_alt_viewer = _touch(tmp_path / "r2352" / "alt.html")
    manual_alt_projection = _touch(tmp_path / "r2352" / "alt.svg")
    interface_model = _touch(tmp_path / "h2312" / "primary.cif")
    interface_viewer = _touch(tmp_path / "h2312" / "viewer.html")
    interface_projection = _touch(tmp_path / "h2312" / "projection.svg")
    probe_model = _touch(tmp_path / "h1311" / "primary.cif")
    probe_viewer = _touch(tmp_path / "h1311" / "viewer.html")
    probe_projection = _touch(tmp_path / "h1311" / "projection.svg")

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
                    "overlay_rank": 1,
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "selector_blocked_manual_review",
                    "overlay_action": "do_not_freeze_model1_external_only",
                    "model1_filename": "manual_primary.cif",
                    "confidence_gap": "0.07",
                    "probe_margin": "-0.23",
                    "probe_result": "probe_fail_model1_displaced",
                    "risk_score": "30.5",
                },
                {
                    "overlay_rank": 2,
                    "target_id": "H2312",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_hold_interface_review",
                    "overlay_action": "keep_model1_hold_until_interface_review",
                    "selected_model_filename": "interface_primary.pdb",
                },
                {
                    "overlay_rank": 3,
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_probe_required",
                    "overlay_action": "run_targeted_no_native_probe_before_freeze",
                    "selected_model_filename": "probe_primary.pdb",
                },
                {
                    "overlay_rank": 4,
                    "target_id": "R2350",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "baseline_calibrated_freeze_ready",
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
                    "target_id": "R2352",
                    "model1_filename": "manual_primary.cif",
                    "alternate_model_filename": "manual_alt.cif",
                },
                {"target_id": "H2312", "selected_model_filename": "interface_primary.pdb"},
                {"target_id": "H1311", "selected_model_filename": "probe_primary.pdb"},
            ],
        },
    )
    _write_json(
        freeze_json,
        {
            "summary": {
                "massivefold_model1_freeze_decision_packet_status": (
                    "massivefold_model1_freeze_decision_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "target_id": "R2352",
                    "alternate_model1_filename": "manual_alt.cif",
                    "top_candidate_filename": "manual_alt.cif",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "rerank_r2352.json",
        _rerank_payload(
            "R2352",
            "manual_primary.cif",
            manual_model,
            manual_viewer,
            manual_projection,
            manifest,
            "manual_alt.cif",
            manual_alt_model,
            manual_alt_viewer,
            manual_alt_projection,
        ),
    )
    _write_json(
        tmp_path / "rerank_h2312.json",
        _rerank_payload(
            "H2312",
            "interface_primary.pdb",
            interface_model,
            interface_viewer,
            interface_projection,
            manifest,
        ),
    )
    _write_json(
        tmp_path / "rerank_h1311.json",
        _rerank_payload("H1311", "probe_primary.pdb", probe_model, probe_viewer, probe_projection, manifest),
    )

    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--model-selection-ledger-json",
            str(ledger_json),
            "--freeze-decision-json",
            str(freeze_json),
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

    assert summary["massivefold_hold_probe_review_packet_status"] == (
        "massivefold_hold_probe_review_packet_ready_external_only"
    )
    assert summary["hold_probe_review_count"] == 3
    assert summary["ready_review_count"] == 3
    assert summary["blocked_review_count"] == 0
    assert summary["manual_blocked_review_count"] == 1
    assert summary["interface_hold_review_count"] == 1
    assert summary["probe_required_review_count"] == 1
    assert summary["alternate_present_count"] == 1
    assert summary["top5_candidate_total"] == 15
    assert summary["first_review_target_id"] == "R2352"
    assert summary["first_review_class"] == "manual_blocked_review"
    assert rows[0]["alternate_model_filename"] == "manual_alt.cif"
    assert rows[0]["blockers"] == ""

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_manual_blocked_review_r2352" / "HOLD_PROBE_REVIEW.md").is_file()


def test_hold_probe_review_packet_blocks_manual_review_without_alternate(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    ledger_json = tmp_path / "ledger.json"
    freeze_json = tmp_path / "freeze.json"
    _write_json(
        overlay_json,
        {
            "rows": [
                {
                    "overlay_rank": 1,
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "selector_blocked_manual_review",
                    "model1_filename": "manual_primary.cif",
                }
            ]
        },
    )
    _write_json(ledger_json, {"rows": [{"target_id": "R2352", "model1_filename": "manual_primary.cif"}]})
    _write_json(freeze_json, {"rows": [{"target_id": "R2352"}]})
    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--model-selection-ledger-json",
            str(ledger_json),
            "--freeze-decision-json",
            str(freeze_json),
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

    assert payload["summary"]["massivefold_hold_probe_review_packet_status"] == (
        "massivefold_hold_probe_review_packet_blocked"
    )
    assert payload["summary"]["blocked_review_count"] == 1
    assert "alternate_model_required_for_manual_block_missing" in payload["rows"][0]["blockers"]
    assert "top5_candidate_count_below_5" in payload["rows"][0]["blockers"]
