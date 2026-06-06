import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_unknown_candidate_triage as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "HEADER    FIXTURE",
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_unknown_candidate_triage_splits_internal_like_from_review_only(tmp_path: Path) -> None:
    _write_pdb(tmp_path / "data" / "internal_structures" / "nightly" / "candidate.pdb")
    _write_pdb(tmp_path / "data" / "internal_structures_refined" / "nightly" / "candidate.pdb")
    _write_pdb(tmp_path / "data" / "public_structures" / "nightly" / "public.pdb")
    _write_pdb(tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_rescue" / "candidate.pdb")
    _write_pdb(tmp_path / "runs" / "gpcr_drd2_repair" / "candidate.pdb")
    _write_pdb(tmp_path / "runs" / "selected_allatom_visual_bundle_assets" / "candidate.pdb")
    _write_pdb(tmp_path / "archives" / "smoke_cleanup_2026-02-22" / "candidate.pdb")
    _write_pdb(tmp_path / "runs" / "other" / "candidate.pdb")
    _write_pdb(tmp_path / "tmp" / "candidate.pdb")
    _write_pdb(tmp_path / "runs" / "casp17_predictions_current" / "T9001TS.pdb")
    _write_json(tmp_path / "current_targets.json", {"rows": [{"target_id": "T9001"}]})
    _write_json(
        tmp_path / "sweep.json",
        {"summary": {"unknown_possible_internal_review_count": 9}},
    )
    _write_json(
        tmp_path / "source_gate.json",
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "first_blocker": "internal_source_id_missing_or_external",
            }
        },
    )

    args = mod.parse_args(
        [
            "--scan-root",
            str(tmp_path),
            "--current-targets-json",
            str(tmp_path / "current_targets.json"),
            "--filesystem-sweep-json",
            str(tmp_path / "sweep.json"),
            "--source-gate-json",
            str(tmp_path / "source_gate.json"),
            "--out-json",
            str(tmp_path / "triage.json"),
            "--out-csv",
            str(tmp_path / "triage.csv"),
            "--out-md",
            str(tmp_path / "triage.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    rows = {row["triage_category"]: row for row in payload["rows"]}

    assert payload["summary"]["unknown_candidate_triage_status"] == (
        "strict_blind_unknown_triage_internal_like_review_required"
    )
    assert payload["summary"]["unknown_possible_internal_review_count"] == 9
    assert payload["summary"]["promotion_ready_count"] == 0
    assert payload["summary"]["internal_like_review_count"] == 2
    assert payload["summary"]["public_structure_count"] == 1
    assert payload["summary"]["run_review_count"] == 4
    assert payload["summary"]["archive_review_count"] == 1
    assert payload["summary"]["tmp_misc_count"] == 1
    assert rows["internal_structure_archive_unverified"]["file_count"] == 2
    assert rows["internal_structure_archive_unverified"]["promotion_ready_count"] == 0
    assert rows["public_structure_archive_not_internal"]["file_count"] == 1
    assert rows["wetlab_ligand_or_allatom_review_only"]["file_count"] == 1
    assert rows["gpcr_repair_or_profile_review_only"]["file_count"] == 1
    assert rows["selected_visual_or_name_index_review_only"]["file_count"] == 1
    assert rows["runs_other_unverified"]["file_count"] == 1
    assert rows["archival_smoke_or_delivery_review_only"]["file_count"] == 1
    assert rows["tmp_or_misc_unverified"]["file_count"] == 1
    assert "internal-like review: `2`" in Path(args.out_md).read_text(encoding="utf-8")
