import json
from pathlib import Path

from tools import build_casp17_massivefold_freeze_candidate_format_preflight as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MODEL\n", encoding="utf-8")
    return str(path)


def _freeze_row(tmp_path: Path, target_id: str, decision_class: str, rank: int, selected: str) -> dict:
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
        "selected_model_filename": selected,
        "model_path": model,
        "viewer_html": viewer,
        "projection_svg": projection,
        "top5_manifest_csv": top5,
        "decision_md": str(tmp_path / target_id.lower() / "decision.md"),
    }


def test_freeze_candidate_format_preflight_checks_ready_freeze_candidates(tmp_path: Path) -> None:
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
                _freeze_row(tmp_path, "H2319", "freeze_candidate_after_probe", 1, "model.pdb"),
                _freeze_row(tmp_path, "R2350", "freeze_candidate_existing", 2, "model.cif"),
                _freeze_row(tmp_path, "R2352", "manual_block", 3, "manual.cif"),
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

    assert summary["massivefold_freeze_candidate_format_preflight_status"] == (
        "massivefold_freeze_candidate_format_preflight_ready_external_only"
    )
    assert summary["freeze_candidate_count"] == 2
    assert summary["ready_preflight_count"] == 2
    assert summary["blocked_preflight_count"] == 0
    assert summary["existing_freeze_candidate_count"] == 1
    assert summary["probe_freeze_candidate_count"] == 1
    assert summary["selected_pdb_count"] == 1
    assert summary["selected_cif_count"] == 1
    assert summary["packaged_cif_count"] == 2
    assert summary["target_id_format_ok_count"] == 2
    assert summary["model_nonempty_count"] == 2
    assert rows[0]["target_id"] == "H2319"
    assert rows[0]["blockers"] == ""

    mod.write_outputs(args, payload)

    assert (tmp_path / "packet.json").is_file()
    assert (tmp_path / "packet.csv").is_file()
    assert (tmp_path / "PACKET.md").is_file()
    assert (tmp_path / "packet.html").is_file()
    assert (tmp_path / "packet" / "01_protein_complex_h2319" / "FORMAT_PREFLIGHT.md").is_file()


def test_freeze_candidate_format_preflight_blocks_missing_files_and_bad_ids(tmp_path: Path) -> None:
    decision_json = tmp_path / "decision.json"
    _write_json(
        decision_json,
        {
            "rows": [
                {
                    "decision_rank": 1,
                    "target_id": "BAD",
                    "target_group": "protein_complex",
                    "decision_class": "freeze_candidate_after_probe",
                    "selected_model_filename": "model.txt",
                    "model_path": str(tmp_path / "missing.txt"),
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

    assert payload["summary"]["massivefold_freeze_candidate_format_preflight_status"] == (
        "massivefold_freeze_candidate_format_preflight_blocked"
    )
    assert payload["summary"]["blocked_preflight_count"] == 1
    assert "target_id_format_invalid" in payload["rows"][0]["blockers"]
    assert "selected_model_extension_unsupported" in payload["rows"][0]["blockers"]
    assert "model_file_missing" in payload["rows"][0]["blockers"]
