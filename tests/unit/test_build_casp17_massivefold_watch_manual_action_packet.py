import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_watch_manual_action_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    return str(path)


def _row(tmp_path: Path, target_id: str, decision_class: str, rank: int) -> dict:
    model = _touch(tmp_path / target_id.lower() / "model.cif")
    viewer = _touch(tmp_path / target_id.lower() / "viewer.html")
    projection = _touch(tmp_path / target_id.lower() / "projection.svg")
    top5 = _touch(tmp_path / target_id.lower() / "top5.csv")
    return {
        "decision_rank": rank,
        "target_id": target_id,
        "target_group": "rna_hybrid" if target_id.startswith("R") else "protein_complex",
        "decision_class": decision_class,
        "final_selector_decision": f"decision_{target_id}",
        "selected_model_filename": f"{target_id}_model.cif",
        "alternate_model_filename": f"{target_id}_alt.cif" if decision_class == "manual_block" else "",
        "probe_result": "probe_watch_model1_retained_low_margin",
        "probe_margin": "0.31",
        "model_path": model,
        "viewer_html": viewer,
        "projection_svg": projection,
        "top5_manifest_csv": top5,
        "decision_md": str(tmp_path / target_id.lower() / "decision.md"),
    }


def test_watch_manual_action_packet_builds_review_actions(tmp_path: Path) -> None:
    decision_json = tmp_path / "decision.json"
    _write_json(
        decision_json,
        {
            "summary": {
                "massivefold_post_probe_selector_decision_packet_status": (
                    "massivefold_post_probe_selector_decision_packet_ready_external_only"
                )
            },
            "rows": [
                _row(tmp_path, "R2352", "manual_block", 1),
                _row(tmp_path, "H2312", "interface_hold", 2),
                _row(tmp_path, "H1311", "watch_low_margin_after_probe", 3),
                _row(tmp_path, "R2350", "freeze_candidate_existing", 4),
                _row(tmp_path, "H2319", "freeze_candidate_after_probe", 5),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--post-probe-selector-decision-json",
            str(decision_json),
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

    assert summary["massivefold_watch_manual_action_packet_status"] == (
        "massivefold_watch_manual_action_packet_ready_external_only"
    )
    assert summary["action_count"] == 3
    assert summary["ready_action_count"] == 3
    assert summary["manual_alternate_review_count"] == 1
    assert summary["interface_geometry_review_count"] == 1
    assert summary["low_margin_top5_review_count"] == 1
    assert summary["priority1_action_count"] == 2
    assert summary["priority2_action_count"] == 1
    assert summary["alternate_present_count"] == 1
    assert summary["first_action_target_id"] == "R2352"
    assert rows[0]["action_class"] == "manual_alternate_review"
    assert rows[1]["action_class"] == "interface_geometry_review"
    assert rows[2]["action_class"] == "low_margin_top5_review"

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_manual_alternate_review_r2352" / "WATCH_MANUAL_ACTION.md").is_file()


def test_watch_manual_action_packet_blocks_missing_artifacts(tmp_path: Path) -> None:
    decision_json = tmp_path / "decision.json"
    _write_json(
        decision_json,
        {
            "rows": [
                {
                    "decision_rank": 1,
                    "target_id": "R2352",
                    "target_group": "rna_hybrid",
                    "decision_class": "manual_block",
                    "selected_model_filename": "missing.cif",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--post-probe-selector-decision-json",
            str(decision_json),
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

    assert payload["summary"]["massivefold_watch_manual_action_packet_status"] == (
        "massivefold_watch_manual_action_packet_blocked"
    )
    assert payload["summary"]["blocked_action_count"] == 1
    assert "model_file_missing" in payload["rows"][0]["blockers"]
    assert "manual_alternate_missing" in payload["rows"][0]["blockers"]
