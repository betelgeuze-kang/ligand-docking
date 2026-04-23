from __future__ import annotations

from tools.build_transporter_membrane_readiness import build_payload


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_membrane_readiness() -> None:
    scaffold_payload = {
        "ok": True,
        "summary": {
            "artifact_count": 12,
            "artifact_exists_count": 12,
            "task_count": 3,
            "profile_count": 2,
        },
    }
    gap_rows = [
        {"target_id": "Aquaporin_1", "priority": "P0", "status": "todo", "required_artifact": "ligand_reference_csv", "proposed_repo_path": "config/a.csv", "notes": "need binders"},
        {"target_id": "Aquaporin_1", "priority": "P0", "status": "todo", "required_artifact": "target_meta_csv", "proposed_repo_path": "config/b.csv", "notes": "need target meta"},
        {"target_id": "GLUT1_4PYP", "priority": "P0", "status": "todo", "required_artifact": "ligand_reference_csv", "proposed_repo_path": "config/c.csv", "notes": "need binders"},
        {"target_id": "GLUT1_4PYP", "priority": "P2", "status": "optional", "required_artifact": "bridge_candidate_review", "proposed_repo_path": "docs/x.md", "notes": "optional"},
    ]
    payload = build_payload(scaffold_payload, gap_rows)
    assert payload["summary"]["validate_only_ok"] is True
    assert payload["summary"]["p0_open_count"] == 3
    rows = {row["target_id"]: row for row in payload["target_rows"]}
    assert rows["Aquaporin_1"]["p0_open_count"] == 2
    assert rows["GLUT1_4PYP"]["p0_open_count"] == 1


def test_build_transporter_membrane_readiness_uses_aqp1_plan_override() -> None:
    scaffold_payload = {
        "ok": True,
        "summary": {
            "artifact_count": 12,
            "artifact_exists_count": 12,
            "task_count": 3,
            "profile_count": 2,
        },
    }
    gap_rows = [
        {"target_id": "Aquaporin_1", "priority": "P0", "status": "todo", "required_artifact": "ligand_reference_csv", "proposed_repo_path": "config/a.csv", "notes": "need binders"},
        {"target_id": "Aquaporin_1", "priority": "P0", "status": "todo", "required_artifact": "target_meta_csv", "proposed_repo_path": "config/b.csv", "notes": "need target meta"},
        {"target_id": "GLUT1_4PYP", "priority": "P0", "status": "todo", "required_artifact": "ligand_reference_csv", "proposed_repo_path": "config/c.csv", "notes": "need binders"},
        {"target_id": "transporter_membrane", "priority": "P0", "status": "todo", "required_artifact": "fit_donor_policy", "proposed_repo_path": "docs/x.md", "notes": "need donor policy"},
    ]
    aqp1_plan = {
        "summary": {"todo_count": 5, "next_priority_steps": ["aqp1_ligand_reference", "aqp1_eval_split"]},
        "rows": [
            {"artifact": "target_native_csv", "status": "ready"},
            {"artifact": "target_meta_csv", "status": "ready"},
            {"artifact": "ligand_reference_csv", "status": "todo"},
            {"artifact": "eval_split_csv", "status": "todo"},
            {"artifact": "ligand_meta_csv", "status": "todo"},
            {"artifact": "profile_json", "status": "ready"},
            {"artifact": "fit_donor_policy", "status": "todo"},
            {"artifact": "smoke_task_binding", "status": "todo"},
        ],
    }
    payload = build_payload(scaffold_payload, gap_rows, aqp1_plan)
    assert payload["summary"]["p0_open_count"] == 5
    rows = {row["target_id"]: row for row in payload["target_rows"]}
    assert rows["Aquaporin_1"]["p0_open_count"] == 3
    _contains_tokens(rows["Aquaporin_1"]["next_required_step"], "aqp1", "ligand packet", "blocker")
