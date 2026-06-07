import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_post_probe_selector_decision_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return str(path)


def _artifact_set(root: Path, name: str) -> dict:
    model = _touch(root / name / "model.cif")
    viewer = _touch(root / name / "viewer.html")
    projection = _touch(root / name / "projection.svg")
    top5 = _touch(root / name / "top5.csv")
    return {
        "model_path": model,
        "viewer_html": viewer,
        "projection_svg": projection,
        "top5_manifest_csv": top5,
    }


def test_post_probe_selector_decision_packet_combines_all_decision_classes(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    freeze_json = tmp_path / "freeze.json"
    hold_json = tmp_path / "hold.json"
    probe_json = tmp_path / "probe.json"
    freeze_artifacts = _artifact_set(tmp_path, "r2350")
    pass_artifacts = _artifact_set(tmp_path, "h2319")
    watch_artifacts = _artifact_set(tmp_path, "h1311")
    interface_artifacts = _artifact_set(tmp_path, "h2312")
    manual_artifacts = _artifact_set(tmp_path, "r2352")

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
                    "model1_filename": "manual_model.cif",
                },
                {
                    "overlay_rank": 2,
                    "target_id": "H2312",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_hold_interface_review",
                    "selected_model_filename": "interface_model.pdb",
                },
                {
                    "overlay_rank": 3,
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_probe_required",
                    "selected_model_filename": "watch_model.pdb",
                },
                {
                    "overlay_rank": 4,
                    "target_id": "H2319",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_probe_required",
                    "selected_model_filename": "pass_model.pdb",
                },
                {
                    "overlay_rank": 5,
                    "target_id": "R2350",
                    "target_group": "rna_hybrid",
                    "overlay_decision": "baseline_calibrated_freeze_ready",
                    "selected_model_filename": "freeze_model.cif",
                },
            ],
        },
    )
    _write_json(
        freeze_json,
        {
            "summary": {
                "massivefold_freeze_ready_review_packet_status": (
                    "massivefold_freeze_ready_review_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "target_id": "R2350",
                    "target_group": "rna_hybrid",
                    "selected_model_filename": "freeze_model.cif",
                    "confidence_score": "83",
                    "probe_margin": "0.64",
                    "review_md": str(tmp_path / "freeze.md"),
                    **freeze_artifacts,
                }
            ],
        },
    )
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
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "review_class": "manual_blocked_review",
                    "primary_model_filename": "manual_model.cif",
                    "alternate_model_filename": "manual_alt.cif",
                    "probe_margin": "-0.23",
                    "review_md": str(tmp_path / "manual.md"),
                    **manual_artifacts,
                },
                {
                    "target_id": "H2312",
                    "target_group": "protein_complex",
                    "review_class": "interface_hold_review",
                    "primary_model_filename": "interface_model.pdb",
                    "probe_margin": "0.10",
                    "review_md": str(tmp_path / "interface.md"),
                    **interface_artifacts,
                },
            ],
        },
    )
    _write_json(
        probe_json,
        {
            "summary": {
                "massivefold_probe_required_targeted_probe_packet_status": (
                    "massivefold_probe_required_targeted_probe_packet_ready_external_only"
                )
            },
            "rows": [
                {
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "primary_model_filename": "watch_model.pdb",
                    "top_candidate_filename": "watch_model.pdb",
                    "probe_result": "probe_watch_model1_retained_low_margin",
                    "probe_margin": "0.31",
                    "probe_md": str(tmp_path / "watch.md"),
                    **watch_artifacts,
                },
                {
                    "target_id": "H2319",
                    "target_group": "protein_complex",
                    "primary_model_filename": "pass_model.pdb",
                    "top_candidate_filename": "pass_model.pdb",
                    "probe_result": "probe_pass_model1_retained_clear",
                    "probe_margin": "1.19",
                    "probe_md": str(tmp_path / "pass.md"),
                    **pass_artifacts,
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--freeze-ready-review-json",
            str(freeze_json),
            "--hold-probe-review-json",
            str(hold_json),
            "--targeted-probe-json",
            str(probe_json),
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

    assert summary["massivefold_post_probe_selector_decision_packet_status"] == (
        "massivefold_post_probe_selector_decision_packet_ready_external_only"
    )
    assert summary["decision_count"] == 5
    assert summary["ready_decision_count"] == 5
    assert summary["freeze_candidate_count"] == 2
    assert summary["watch_decision_count"] == 2
    assert summary["manual_block_decision_count"] == 1
    assert summary["existing_freeze_candidate_count"] == 1
    assert summary["probe_freeze_candidate_count"] == 1
    assert summary["probe_watch_count"] == 1
    assert summary["interface_hold_count"] == 1
    assert summary["manual_block_count"] == 1
    assert summary["first_decision_target_id"] == "R2352"
    assert rows[0]["decision_class"] == "manual_block"
    assert rows[1]["decision_class"] == "interface_hold"
    assert rows[2]["decision_class"] == "watch_low_margin_after_probe"
    assert rows[3]["decision_class"] == "freeze_candidate_after_probe"
    assert rows[4]["decision_class"] == "freeze_candidate_existing"

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_manual_block_r2352" / "SELECTOR_DECISION.md").is_file()


def test_post_probe_selector_decision_packet_blocks_missing_artifacts(tmp_path: Path) -> None:
    overlay_json = tmp_path / "overlay.json"
    freeze_json = tmp_path / "freeze.json"
    hold_json = tmp_path / "hold.json"
    probe_json = tmp_path / "probe.json"
    _write_json(
        overlay_json,
        {
            "rows": [
                {
                    "overlay_rank": 1,
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "overlay_decision": "selector_probe_required",
                    "selected_model_filename": "missing.pdb",
                }
            ]
        },
    )
    _write_json(freeze_json, {"rows": []})
    _write_json(hold_json, {"rows": []})
    _write_json(
        probe_json,
        {
            "rows": [
                {
                    "target_id": "H1311",
                    "target_group": "protein_complex",
                    "primary_model_filename": "missing.pdb",
                    "top_candidate_filename": "missing.pdb",
                    "probe_result": "probe_pass_model1_retained_clear",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--selector-overlay-json",
            str(overlay_json),
            "--freeze-ready-review-json",
            str(freeze_json),
            "--hold-probe-review-json",
            str(hold_json),
            "--targeted-probe-json",
            str(probe_json),
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

    assert payload["summary"]["massivefold_post_probe_selector_decision_packet_status"] == (
        "massivefold_post_probe_selector_decision_packet_blocked"
    )
    assert payload["summary"]["blocked_decision_count"] == 1
    assert "model_file_missing" in payload["rows"][0]["blockers"]
    assert "top5_manifest_missing" in payload["rows"][0]["blockers"]
