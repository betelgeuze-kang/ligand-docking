import hashlib
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_freeze_candidate_escrow as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "MODEL\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_massivefold_freeze_candidate_escrow_hashes_ready_candidates(tmp_path: Path) -> None:
    h_model = Path(_touch(tmp_path / "h2319" / "model.cif", "ATOM H2319\n"))
    h_top5 = Path(_touch(tmp_path / "h2319" / "top5.csv", "rank,model\n1,H2319\n"))
    h_viewer = _touch(tmp_path / "h2319" / "viewer.html")
    h_projection = _touch(tmp_path / "h2319" / "projection.svg")
    r_model = Path(_touch(tmp_path / "r2350" / "model.cif", "ATOM R2350\n"))
    r_top5 = Path(_touch(tmp_path / "r2350" / "top5.csv", "rank,model\n1,R2350\n"))
    r_viewer = _touch(tmp_path / "r2350" / "viewer.html")
    r_projection = _touch(tmp_path / "r2350" / "projection.svg")
    preflight_json = tmp_path / "preflight.json"

    _write_json(
        preflight_json,
        {
            "summary": {
                "massivefold_freeze_candidate_format_preflight_status": (
                    "massivefold_freeze_candidate_format_preflight_ready_external_only"
                ),
                "existing_freeze_candidate_count": 1,
                "probe_freeze_candidate_count": 1,
            },
            "rows": [
                {
                    "preflight_rank": 1,
                    "preflight_status": "freeze_candidate_format_preflight_ready_external_only",
                    "target_group": "protein_complex",
                    "target_id": "H2319",
                    "decision_class": "freeze_candidate_after_probe",
                    "final_selector_decision": "external_model1_freeze_candidate_after_targeted_probe",
                    "selected_model_filename": "model.pdb",
                    "model_path": str(h_model),
                    "top5_manifest_csv": str(h_top5),
                    "viewer_html": h_viewer,
                    "projection_svg": h_projection,
                    "preflight_md": "casp17/preflight/H2319.md",
                    "source_decision_md": "casp17/decision/H2319.md",
                },
                {
                    "preflight_rank": 2,
                    "preflight_status": "freeze_candidate_format_preflight_ready_external_only",
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "decision_class": "freeze_candidate_existing",
                    "final_selector_decision": "external_model1_selected_conditional",
                    "selected_model_filename": "model.cif",
                    "model_path": str(r_model),
                    "top5_manifest_csv": str(r_top5),
                    "viewer_html": r_viewer,
                    "projection_svg": r_projection,
                },
            ],
        },
    )

    args = mod.parse_args(
        [
            "--freeze-candidate-preflight-json",
            str(preflight_json),
            "--out-dir",
            str(tmp_path / "escrow"),
            "--out-json",
            str(tmp_path / "escrow.json"),
            "--out-csv",
            str(tmp_path / "escrow.csv"),
            "--out-md",
            str(tmp_path / "ESCROW.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["massivefold_freeze_candidate_escrow_status"] == (
        "massivefold_freeze_candidate_escrow_ready_external_only"
    )
    assert summary["escrow_count"] == 2
    assert summary["ready_escrow_count"] == 2
    assert summary["blocked_escrow_count"] == 0
    assert summary["model_sha256_count"] == 2
    assert summary["top5_sha256_count"] == 2
    assert summary["existing_freeze_candidate_count"] == 1
    assert summary["probe_freeze_candidate_count"] == 1
    assert summary["protein_complex_escrow_count"] == 1
    assert summary["rna_hybrid_escrow_count"] == 1
    assert summary["native_pending_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert rows["H2319"]["model_sha256"] == _sha(h_model)
    assert rows["R2350"]["top5_manifest_sha256"] == _sha(r_top5)
    assert rows["H2319"]["competitive_proof_eligible"] == "false"

    assert (tmp_path / "escrow.json").is_file()
    assert (tmp_path / "escrow.csv").is_file()
    assert (tmp_path / "ESCROW.md").is_file()
    assert (tmp_path / "escrow" / "01_protein_complex_h2319" / "FREEZE_ESCROW.md").is_file()
    assert "AUTHOR " not in (tmp_path / "escrow.json").read_text(encoding="utf-8")


def test_massivefold_freeze_candidate_escrow_blocks_missing_artifacts(tmp_path: Path) -> None:
    preflight_json = tmp_path / "preflight.json"
    _write_json(
        preflight_json,
        {
            "rows": [
                {
                    "preflight_rank": 1,
                    "preflight_status": "freeze_candidate_format_preflight_blocked",
                    "target_group": "rna_hybrid",
                    "target_id": "R2352",
                    "decision_class": "freeze_candidate_after_probe",
                    "model_path": str(tmp_path / "missing.cif"),
                    "top5_manifest_csv": str(tmp_path / "missing.csv"),
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--freeze-candidate-preflight-json",
            str(preflight_json),
            "--out-dir",
            str(tmp_path / "escrow"),
            "--out-json",
            str(tmp_path / "escrow.json"),
            "--out-csv",
            str(tmp_path / "escrow.csv"),
            "--out-md",
            str(tmp_path / "ESCROW.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_freeze_candidate_escrow_status"] == (
        "massivefold_freeze_candidate_escrow_blocked"
    )
    assert payload["summary"]["blocked_escrow_count"] == 1
    assert "freeze_candidate_preflight_not_ready" in payload["rows"][0]["blockers"]
    assert "model_file_missing" in payload["rows"][0]["blockers"]
    assert "top5_manifest_missing" in payload["rows"][0]["blockers"]
