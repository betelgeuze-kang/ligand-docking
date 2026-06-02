from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_3d_ligand_metric_gap_bridge as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--metric-handoff-json",
        str(tmp_path / "metric_handoff.json"),
        "--organic-candidate-json",
        str(tmp_path / "organic_candidates.json"),
        "--organic-promotion-json",
        str(tmp_path / "organic_promotion.json"),
        "--out-dir",
        str(tmp_path / "bridge"),
        "--out-json",
        str(tmp_path / "bridge.json"),
        "--out-csv",
        str(tmp_path / "bridge.csv"),
        "--out-md",
        str(tmp_path / "BRIDGE.md"),
    ]


def _candidate(rank: int, candidate_id: str, *, affinity: bool = True) -> dict[str, str]:
    return {
        "candidate_rank": str(rank),
        "candidate_id": candidate_id,
        "target_id": f"HIST_COMPLEX_{rank:02d}",
        "ligand_id": f"ligand_{rank:02d}",
        "ligand_source_dataset": "ChEMBL" if affinity else "BindingDB",
        "review_ready": "True",
        "competitive_proof_eligible": "False",
        "strict_blind_promotion_status": "blocked_homolog_source_no_leak_and_chronology_required",
        "lddt_pli_required": "True",
        "bisyrmsd_required": "True",
        "local_reference_present": "True",
        "prediction_present": "True",
        "ligand_mol2_present": "True",
        "ligand_template_present": "True",
        "candidate_manifest": f"candidate/{candidate_id}/CANDIDATE.md",
        "candidate_folder": f"candidate/{candidate_id}",
    }


def _actions(candidate_id: str, target_id: str, ligand_id: str, start: int) -> list[dict[str, str]]:
    specs = [
        ("direct_native_or_source_authority", "open_operator_evidence_required"),
        ("no_leak_provenance", "open_operator_evidence_required"),
        ("prediction_chronology", "open_operator_evidence_required"),
        ("ligand_pose_reference", "open_operator_evidence_required"),
        ("lddt_pli_metric_inputs", "open_metric_input_required"),
        ("bisyrmsd_metric_inputs", "open_metric_input_required"),
        ("strict_blind_slot_mapping", "open_slot_mapping_required"),
    ]
    rows = []
    for offset, (action_type, status) in enumerate(specs, start=start):
        rows.append(
            {
                "action_rank": str(offset),
                "candidate_id": candidate_id,
                "target_id": target_id,
                "ligand_id": ligand_id,
                "action_id": f"action_{offset:03d}",
                "action_type": action_type,
                "action_status": status,
                "action_md": f"actions/{candidate_id}/{action_type}/ACTION.md",
            }
        )
    return rows


def test_3d_ligand_metric_gap_bridge_maps_missing_metrics_to_organic_actions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    candidates = [_candidate(1, "organic_001"), _candidate(2, "organic_002", affinity=False)]
    actions = []
    for index, candidate in enumerate(candidates):
        actions.extend(
            _actions(
                candidate["candidate_id"],
                candidate["target_id"],
                candidate["ligand_id"],
                index * 10 + 1,
            )
        )
    _write_json(
        tmp_path / "metric_handoff.json",
        {
            "summary": {
                "metric_handoff_status": "casp17_3d_molecular_object_metric_handoff_ready_review_only_ligand_gap",
                "missing_required_metric_names": "LDDT-PLI,BiSyRMSD",
            }
        },
    )
    _write_json(
        tmp_path / "organic_candidates.json",
        {
            "summary": {
                "organic_ligand_slot_candidate_status": "organic_ligand_slot_candidates_ready_for_operator_review",
                "candidate_count": 2,
                "review_ready_candidate_count": 2,
                "competitive_proof_eligible_count": 0,
                "strict_blind_promotion_blocked_count": 2,
            },
            "rows": candidates,
        },
    )
    _write_json(
        tmp_path / "organic_promotion.json",
        {
            "summary": {
                "organic_ligand_slot_promotion_action_board_status": "awaiting_organic_ligand_strict_blind_evidence"
            },
            "rows": actions,
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["ligand_metric_gap_bridge_status"] == (
        "ligand_metric_gap_mapped_awaiting_strict_blind_evidence"
    )
    assert payload["summary"]["missing_ligand_metric_names"] == "LDDT-PLI,BiSyRMSD"
    assert payload["summary"]["bridge_row_count"] == 4
    assert payload["summary"]["blocked_bridge_row_count"] == 4
    assert payload["summary"]["lddt_pli_bridge_row_count"] == 2
    assert payload["summary"]["bisyrmsd_bridge_row_count"] == 2
    assert payload["summary"]["metric_action_link_count"] == 4
    assert payload["summary"]["proof_eligible_candidate_count"] == 0
    first = payload["rows"][0]
    assert first["metric_action_md"].endswith("lddt_pli_metric_inputs/ACTION.md")
    assert "candidate_not_competitive_proof_eligible" in first["blockers"]
    assert "direct_native_or_source_authority_open" in first["blockers"]
    assert "does not create ligand native objects" in payload["summary"]["claim_boundary"]
    assert (tmp_path / "bridge.json").is_file()
    assert (tmp_path / "bridge.csv").is_file()
    assert (tmp_path / "BRIDGE.md").is_file()
    assert (tmp_path / "bridge/lddt_pli/BRIDGE.md").is_file()
    assert (tmp_path / "bridge/bisyrmsd/BRIDGE.md").is_file()


def test_3d_ligand_metric_gap_bridge_reports_closed_gap_when_no_missing_ligand_metrics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "metric_handoff.json",
        {"summary": {"missing_required_metric_names": ""}},
    )
    _write_json(tmp_path / "organic_candidates.json", {"summary": {}, "rows": []})
    _write_json(tmp_path / "organic_promotion.json", {"summary": {}, "rows": []})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["ligand_metric_gap_bridge_status"] == "ligand_metric_gap_not_open_in_3d_handoff"
    assert payload["summary"]["bridge_row_count"] == 0
    assert payload["rows"] == []
