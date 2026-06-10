from tools.accounting.build_pxr_defer_exact_evidence_operator_fill_guide import (
    DEFER_OPERATOR_GUIDANCE,
    build_intake_rows,
    build_payload,
)


def test_build_intake_rows_for_must_remain_deferred() -> None:
    rows = build_intake_rows(
        [
            {
                "manual_commit_class": "must_remain_deferred",
                "packet_step": "core_eval_non_binder_01",
                "ligand": "acetaminophen",
                "binder": "0",
                "manual_promotion_blocker": "activity_proxy_conflict",
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0]["review_decision"] == "KEEP_BLOCKED"
    assert rows[0]["conflict_resolution_decision"] == "KEEP_DEFERRED"
    assert rows[0]["replacement_reference_binding_kcal_mol"] == "KEEP_BLOCKED"
    assert "activity proxy" in rows[0]["reviewer_notes"].lower()


def test_build_payload_includes_all_defer_guidance_steps() -> None:
    payload = build_payload(
        {
            "rows": [
                {
                    "manual_commit_class": "must_remain_deferred",
                    "packet_step": step,
                    "ligand": guidance["candidate_name"],
                    "binder": "0",
                }
                for step, guidance in DEFER_OPERATOR_GUIDANCE.items()
            ]
        }
    )
    assert payload["summary"]["defer_row_count"] == 3
    assert payload["summary"]["operator_fill_policy"] == "KEEP_DEFERRED_or_exact_evidence_only"
