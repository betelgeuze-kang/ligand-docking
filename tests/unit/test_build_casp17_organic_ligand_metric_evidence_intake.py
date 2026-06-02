from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_organic_ligand_metric_evidence_intake as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bridge_row(rank: int, candidate_id: str, metric: str) -> dict[str, str]:
    return {
        "bridge_rank": str(rank),
        "candidate_rank": "1" if candidate_id.endswith("001") else "2",
        "candidate_id": candidate_id,
        "target_id": "HIST_COMPLEX_01" if candidate_id.endswith("001") else "HIST_COMPLEX_02",
        "ligand_id": "ligand_001" if candidate_id.endswith("001") else "ligand_002",
        "ligand_source_dataset": "ChEMBL",
        "missing_metric_name": metric,
        "metric_action_md": f"actions/{candidate_id}/{metric}/ACTION.md",
    }


def _promotion_action(candidate_id: str, action_type: str, rank: int, *, ready: bool = False) -> dict[str, str]:
    status = "operator_evidence_ready" if ready else "open_operator_evidence_required"
    if action_type == "strict_blind_slot_mapping" and not ready:
        status = "open_slot_mapping_required"
    return {
        "action_rank": str(rank),
        "action_id": f"action_{rank:03d}",
        "candidate_id": candidate_id,
        "target_id": "HIST_COMPLEX_01" if candidate_id.endswith("001") else "HIST_COMPLEX_02",
        "ligand_id": "ligand_001" if candidate_id.endswith("001") else "ligand_002",
        "ligand_source_dataset": "ChEMBL",
        "action_type": action_type,
        "action_status": status,
        "action_md": f"actions/{candidate_id}/{action_type}/ACTION.md",
        "current_evidence": "current evidence",
        "required_artifact": f"required {action_type}",
    }


def _write_inputs(tmp_path: Path, *, ready: bool = False) -> tuple[Path, Path]:
    bridge = tmp_path / "bridge.json"
    promotion = tmp_path / "promotion.json"
    candidates = ["organic_ligand_slot_candidate_001", "organic_ligand_slot_candidate_002"]
    _write_json(
        bridge,
        {
            "summary": {"ligand_metric_gap_bridge_status": "ligand_metric_gap_mapped"},
            "rows": [
                _bridge_row(1, candidates[0], "LDDT-PLI"),
                _bridge_row(2, candidates[0], "BiSyRMSD"),
                _bridge_row(3, candidates[1], "LDDT-PLI"),
                _bridge_row(4, candidates[1], "BiSyRMSD"),
            ],
        },
    )
    rows = []
    rank = 1
    for candidate_id in candidates:
        for action_type in mod.REQUIRED_FIELD_TYPES:
            rows.append(_promotion_action(candidate_id, action_type, rank, ready=ready))
            rank += 1
    _write_json(
        promotion,
        {
            "summary": {
                "organic_ligand_slot_promotion_action_board_status": (
                    "awaiting_organic_ligand_strict_blind_evidence"
                )
            },
            "rows": rows,
        },
    )
    return bridge, promotion


def _args(tmp_path: Path, bridge: Path, promotion: Path) -> list[str]:
    return [
        "--ligand-bridge-json",
        str(bridge),
        "--organic-promotion-json",
        str(promotion),
        "--packet-root",
        str(tmp_path / "packets"),
        "--out-json",
        str(tmp_path / "intake.json"),
        "--out-csv",
        str(tmp_path / "intake.csv"),
        "--out-md",
        str(tmp_path / "INTAKE.md"),
    ]


def test_organic_ligand_metric_evidence_intake_writes_candidate_templates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    bridge, promotion = _write_inputs(tmp_path)
    args = mod.parse_args(_args(tmp_path, bridge, promotion))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_metric_evidence_intake_status"] == (
        "awaiting_organic_ligand_metric_evidence_intake"
    )
    assert summary["candidate_count"] == 2
    assert summary["field_count"] == 10
    assert summary["open_field_count"] == 10
    assert summary["ready_field_count"] == 0
    assert summary["operator_template_count"] == 2
    assert summary["evidence_stub_count"] == 10
    assert summary["dropzone_manifest_count"] == 2
    assert summary["metric_bridge_row_count"] == 4
    assert summary["lddt_pli_bridge_row_count"] == 2
    assert summary["bisyrmsd_bridge_row_count"] == 2
    assert summary["direct_authority_field_count"] == 2
    assert summary["no_leak_field_count"] == 2
    assert summary["chronology_field_count"] == 2
    assert summary["ligand_pose_field_count"] == 2
    assert summary["strict_slot_field_count"] == 2
    assert summary["linked_action_count"] == 10
    assert summary["first_open_field_key"] == "direct_native_or_source_authority"
    assert payload["rows"][0]["evidence_request_kind"] == "direct_native_or_same_system_source_authority"
    assert payload["rows"][0]["packet_folder"].endswith("01_ligand_001")
    assert (tmp_path / "intake.json").is_file()
    assert (tmp_path / "intake.csv").is_file()
    assert (tmp_path / "INTAKE.md").is_file()
    assert (tmp_path / "packets/01_ligand_001/ACTION.md").is_file()
    assert (tmp_path / "packets/01_ligand_001/operator_evidence_template.csv").is_file()
    assert (tmp_path / "packets/01_ligand_001/dropzone_manifest.csv").is_file()
    assert (tmp_path / "packets/01_ligand_001/field_evidence/no_leak_provenance.md").is_file()


def test_organic_ligand_metric_evidence_intake_ready_when_actions_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    bridge, promotion = _write_inputs(tmp_path, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, bridge, promotion)))

    assert payload["summary"]["organic_ligand_metric_evidence_intake_status"] == (
        "organic_ligand_metric_evidence_ready_for_review"
    )
    assert payload["summary"]["ready_candidate_count"] == 2
    assert payload["summary"]["open_field_count"] == 0
    assert {row["field_status"] for row in payload["rows"]} == {"evidence_ready_for_operator_review"}


def test_organic_ligand_metric_evidence_intake_blocks_missing_bridge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    promotion = tmp_path / "promotion.json"
    _write_json(promotion, {"summary": {}, "rows": []})

    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_bridge.json", promotion))
    )

    assert payload["summary"]["organic_ligand_metric_evidence_intake_status"] == (
        "blocked_ligand_metric_gap_bridge_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []
