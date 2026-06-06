from __future__ import annotations

from pathlib import Path


def test_refresh_chain_includes_aqp1_reviewer_workbench_step() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    reviewer_step = '(\"aqp1_reviewer_workbench\", [sys.executable, _script(\"product/build_aqp1_reviewer_workbench.py\")])'
    manual_handoff_step = '(\"aqp1_manual_handoff\", [sys.executable, _script(\"product/build_aqp1_manual_verdict_handoff_packet.py\")])'
    catalog_step = '(\"family_packet_catalog\", [sys.executable, _script(\"build_family_packet_catalog.py\")])'

    assert reviewer_step in text
    assert manual_handoff_step in text
    assert catalog_step in text
    assert text.index(manual_handoff_step) < text.index(reviewer_step) < text.index(catalog_step)


def test_refresh_chain_includes_aqp1_source_confirmation_after_quantitative_provenance() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    quant_step = '(\"aqp1_quantitative_provenance_packet\", [sys.executable, _script(\"product/build_aqp1_quantitative_provenance_packet.py\")])'
    confirmation_step = '(\"aqp1_first_wave_source_confirmation_packet\", [sys.executable, _script(\"product/build_aqp1_first_wave_source_confirmation_packet.py\")])'
    ledger_step = '(\"aqp1_candidate_ledger\", [sys.executable, _script(\"product/build_aqp1_candidate_evidence_ledger.py\")])'

    assert quant_step in text
    assert confirmation_step in text
    assert ledger_step in text
    assert text.index(quant_step) < text.index(confirmation_step) < text.index(ledger_step)


def test_refresh_chain_includes_aqp1_follow_on_after_seed_sync_preview() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    seed_sync_step = '(\"aqp1_seed_sync_preview\", [sys.executable, _script(\"build_aqp1_seed_row_sync_apply_preview.py\")])'
    follow_on_step = '(\"aqp1_first_wave_follow_on_packet\", [sys.executable, _script(\"build_aqp1_first_wave_follow_on_packet.py\")])'
    execution_step = '(\"transporter_seed_execution\", [sys.executable, _script(\"build_transporter_seed_row_execution_packet.py\")])'

    assert seed_sync_step in text
    assert follow_on_step in text
    assert execution_step in text
    assert text.index(seed_sync_step) < text.index(follow_on_step) < text.index(execution_step)


def test_refresh_chain_includes_aqp1_follow_on_source_confirmation_before_blocker_decomposition() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    follow_on_step = '(\"aqp1_first_wave_follow_on_packet\", [sys.executable, _script(\"build_aqp1_first_wave_follow_on_packet.py\")])'
    source_confirmation_step = '(\"aqp1_follow_on_source_confirmation_packet\", [sys.executable, _script(\"build_aqp1_follow_on_source_confirmation_packet.py\")])'
    decomposition_step = '(\"aqp1_follow_on_blocker_decomposition\", [sys.executable, _script(\"product/build_aqp1_follow_on_blocker_decomposition.py\")])'
    execution_step = '(\"transporter_seed_execution\", [sys.executable, _script(\"build_transporter_seed_row_execution_packet.py\")])'

    assert follow_on_step in text
    assert source_confirmation_step in text
    assert decomposition_step in text
    assert execution_step in text
    assert text.index(follow_on_step) < text.index(source_confirmation_step) < text.index(decomposition_step) < text.index(execution_step)


def test_refresh_chain_includes_transporter_commercialization_closure_steps() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    queue_step = '(\"transporter_commercialization_closure_queue\", [sys.executable, _script(\"build_transporter_commercialization_closure_queue.py\")])'
    placeholder_queue_step = '(\"transporter_placeholder_burndown_queue\", [sys.executable, _script(\"build_transporter_placeholder_burndown_queue.py\")])'
    readiness_step = '(\"commercialization_readiness\", [sys.executable, _script(\"build_commercialization_readiness_report.py\")])'
    gap_step = '(\"commercialization_gap_burndown\", [sys.executable, _script(\"build_commercialization_gap_burndown.py\")])'
    rollup_step = '(\"family_expansion_rollup\", [sys.executable, _script(\"build_family_expansion_status_rollup.py\")])'

    assert queue_step in text
    assert placeholder_queue_step in text
    assert readiness_step in text
    assert gap_step in text
    assert rollup_step in text
    assert text.index(queue_step) < text.index(placeholder_queue_step) < text.index(readiness_step) < text.index(gap_step) < text.index(rollup_step)


def test_refresh_chain_runs_local_engine_queue_before_execution_handoff_dashboard() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    placeholder_queue_step = '(\"transporter_placeholder_burndown_queue\", [sys.executable, _script(\"build_transporter_placeholder_burndown_queue.py\")])'
    negative_queue_step = '(\"transporter_negative_evidence_closure_queue\", [sys.executable, _script(\"build_transporter_negative_evidence_closure_queue.py\")])'
    nightly_gate_step = '(\"nightly_gate_burndown_packet\", [sys.executable, _script(\"build_nightly_gate_burndown_packet.py\")])'
    claim_handoff_step = '(\"allatom_claim_evidence_handoff\", [sys.executable, _script(\"build_allatom_claim_evidence_handoff.py\")])'
    review_step = '(\"wetlab_tcruzi_pde_allatom_review_packet\", [sys.executable, _script(\"build_wetlab_tcruzi_pde_allatom_review_packet.py\")])'
    bindingdb_seed_step = '\"wetlab_tcruzi_pde_bindingdb_similarity_seed_packet\"'
    external_rescue_queue_step = '\"wetlab_tcruzi_pde_external_geometry_stability_rescue_queue\"'
    translation_probe_step = '\"wetlab_tcruzi_pde_translation_evidence_probe\"'
    translation_quality_step = '(\"wetlab_tcruzi_pde_translation_quality_packet\", [sys.executable, _script(\"build_wetlab_tcruzi_pde_translation_quality_packet.py\")])'
    metric_scale_step = '\"wetlab_tcruzi_pde_metric_scale_gap_packet\"'
    pose_backmapping_queue_step = '\"wetlab_tcruzi_pde_pose_backmapping_closure_queue\"'
    ligand_atomization_step = '\"wetlab_tcruzi_pde_ligand_atomization_gap_packet\"'
    atomized_draft_step = '\"wetlab_tcruzi_pde_atomized_ligand_draft_packet\"'
    wetlab_selected_step = '(\"wetlab_selected_allatom_gate_burndown_packet\", [sys.executable, _script(\"build_wetlab_selected_allatom_gate_burndown_packet.py\")])'
    wetlab_repair_step = '(\"wetlab_selected_allatom_repair_packet\", [sys.executable, _script(\"build_wetlab_selected_allatom_repair_packet.py\")])'
    wetlab_queue_step = '(\"wetlab_execution_readiness_queue\", [sys.executable, _script(\"build_wetlab_execution_readiness_queue.py\")])'
    local_engine_step = '(\"local_engine_commercialization_queue\", [sys.executable, _script(\"build_local_engine_commercialization_queue.py\")])'
    execution_step = '(\"execution_handoff_dashboard\", [sys.executable, _script(\"build_execution_handoff_dashboard.py\")])'

    assert placeholder_queue_step in text
    assert negative_queue_step in text
    assert nightly_gate_step in text
    assert claim_handoff_step in text
    assert review_step in text
    assert bindingdb_seed_step in text
    assert external_rescue_queue_step in text
    assert translation_probe_step in text
    assert translation_quality_step in text
    assert metric_scale_step in text
    assert pose_backmapping_queue_step in text
    assert ligand_atomization_step in text
    assert atomized_draft_step in text
    assert wetlab_selected_step in text
    assert wetlab_repair_step in text
    assert wetlab_queue_step in text
    assert local_engine_step in text
    assert execution_step in text
    assert text.index(placeholder_queue_step) < text.index(negative_queue_step) < text.index(nightly_gate_step) < text.index(claim_handoff_step) < text.index(review_step) < text.index(bindingdb_seed_step) < text.index(external_rescue_queue_step) < text.index(translation_probe_step) < text.index(translation_quality_step) < text.index(metric_scale_step) < text.index(pose_backmapping_queue_step) < text.index(ligand_atomization_step) < text.index(atomized_draft_step) < text.index(wetlab_selected_step) < text.index(wetlab_repair_step) < text.index(wetlab_queue_step) < text.index(local_engine_step) < text.index(execution_step)


def test_refresh_chain_includes_nightly_stage6_tuning_packet_after_gate_packet() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    nightly_gate_step = '(\"nightly_gate_burndown_packet\", [sys.executable, _script(\"build_nightly_gate_burndown_packet.py\")])'
    nightly_tuning_step = '(\"nightly_stage6_tuning_packet\", [sys.executable, _script(\"build_nightly_stage6_tuning_packet.py\")])'
    nightly_followup_step = '(\"nightly_stage6_followup_retry_packet\", [sys.executable, _script(\"build_nightly_stage6_followup_retry_packet.py\")])'
    nightly_sweep_step = '(\"nightly_stage6_tuning_sweep_packet\", [sys.executable, _script(\"build_nightly_stage6_tuning_sweep_packet.py\")])'
    nightly_probe_step = '(\"nightly_stage6_probe_result_packet\", [sys.executable, _script(\"build_nightly_stage6_probe_result_packet.py\")])'
    nightly_promotion_step = '(\"nightly_stage6_probe_promotion_packet\", [sys.executable, _script(\"build_nightly_stage6_probe_promotion_packet.py\")])'
    nightly_realization_step = '(\"nightly_stage6_realization_packet\", [sys.executable, _script(\"build_nightly_stage6_realization_packet.py\")])'
    nightly_rescored_step = '(\"nightly_stage6_rescored_gate_packet\", [sys.executable, _script(\"build_nightly_stage6_rescored_gate_packet.py\")])'
    nightly_downstream_step = '(\"nightly_stage6_downstream_rerun_packet\", [sys.executable, _script(\"build_nightly_stage6_downstream_rerun_packet.py\")])'
    wetlab_queue_step = '(\"wetlab_execution_readiness_queue\", [sys.executable, _script(\"build_wetlab_execution_readiness_queue.py\")])'

    assert nightly_gate_step in text
    assert nightly_tuning_step in text
    assert nightly_followup_step in text
    assert nightly_sweep_step in text
    assert nightly_probe_step in text
    assert nightly_promotion_step in text
    assert nightly_realization_step in text
    assert nightly_rescored_step in text
    assert nightly_downstream_step in text
    assert wetlab_queue_step in text
    assert text.index(nightly_gate_step) < text.index(nightly_tuning_step) < text.index(nightly_followup_step) < text.index(nightly_sweep_step) < text.index(nightly_probe_step) < text.index(nightly_promotion_step) < text.index(nightly_realization_step) < text.index(nightly_rescored_step) < text.index(nightly_downstream_step) < text.index(wetlab_queue_step)


def test_refresh_chain_includes_glut1_second_wave_source_confirmation_before_placeholder_queue() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    glut1_step = '(\"glut1_second_wave_source_confirmation_packet\", [sys.executable, _script(\"build_glut1_second_wave_source_confirmation_packet.py\")])'
    placeholder_queue_step = '(\"transporter_placeholder_burndown_queue\", [sys.executable, _script(\"build_transporter_placeholder_burndown_queue.py\")])'
    readiness_step = '(\"commercialization_readiness\", [sys.executable, _script(\"build_commercialization_readiness_report.py\")])'

    assert glut1_step in text
    assert placeholder_queue_step in text
    assert readiness_step in text
    assert text.index(glut1_step) < text.index(placeholder_queue_step) < text.index(readiness_step)


def test_refresh_chain_includes_transporter_negative_target_packets_before_family_packet_catalog() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    negative_day_plan_step = '(\"transporter_negative_day_plan\", [sys.executable, _script(\"product/build_transporter_negative_reviewer_day_plan.py\")])'
    target_packets_step = '(\"transporter_negative_target_packets\", [sys.executable, _script(\"build_transporter_negative_evidence_target_packets.py\")])'
    catalog_step = '(\"family_packet_catalog\", [sys.executable, _script(\"build_family_packet_catalog.py\")])'

    assert negative_day_plan_step in text
    assert target_packets_step in text
    assert catalog_step in text
    assert text.index(negative_day_plan_step) < text.index(target_packets_step) < text.index(catalog_step)


def test_refresh_chain_includes_aqp1_negative_source_exclusion_before_transporter_negative_day_plan() -> None:
    refresh_script = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "run_family_expansion_refresh.py"
    )
    text = refresh_script.read_text(encoding="utf-8")

    aqp1_negative_handoff_step = '(\"aqp1_negative_handoff\", [sys.executable, _script(\"product/build_aqp1_negative_review_handoff_packet.py\")])'
    exclusion_step = '(\"aqp1_negative_source_exclusion\", [sys.executable, _script(\"product/build_aqp1_negative_source_exclusion_packet.py\")])'
    slot_closure_step = '(\"aqp1_negative_slot_closure\", [sys.executable, _script(\"product/build_aqp1_negative_slot_closure_packet.py\")])'
    acquisition_step = '(\"aqp1_negative_acquisition\", [sys.executable, _script(\"product/build_aqp1_negative_evidence_acquisition_packet.py\")])'
    confirmation_step = '(\"aqp1_negative_confirmation\", [sys.executable, _script(\"product/build_aqp1_negative_evidence_confirmation_packet.py\")])'
    slot_resolution_step = '(\"aqp1_negative_slot_resolution\", [sys.executable, _script(\"product/build_aqp1_negative_slot_resolution_packet.py\")])'
    frontier_step = '(\"aqp1_negative_candidate_frontier\", [sys.executable, _script(\"product/build_aqp1_negative_candidate_frontier_packet.py\")])'
    frontier_resolution_step = '(\"aqp1_negative_frontier_resolution\", [sys.executable, _script(\"product/build_aqp1_negative_frontier_resolution_packet.py\")])'
    primary_probe_step = '(\"aqp1_negative_primary_probe\", [sys.executable, _script(\"product/build_aqp1_negative_primary_probe_packet.py\")])'
    exact_source_outcome_step = '(\"aqp1_negative_exact_source_outcome\", [sys.executable, _script(\"product/build_aqp1_negative_exact_source_outcome_packet.py\")])'
    primary_probe_resolution_step = '(\"aqp1_negative_primary_probe_resolution\", [sys.executable, _script(\"product/build_aqp1_negative_primary_probe_resolution_packet.py\")])'
    glut1_negative_handoff_step = '(\"glut1_negative_handoff\", [sys.executable, _script(\"product/build_glut1_negative_review_handoff_packet.py\")])'
    negative_day_plan_step = '(\"transporter_negative_day_plan\", [sys.executable, _script(\"product/build_transporter_negative_reviewer_day_plan.py\")])'

    assert aqp1_negative_handoff_step in text
    assert exclusion_step in text
    assert slot_closure_step in text
    assert acquisition_step in text
    assert confirmation_step in text
    assert slot_resolution_step in text
    assert frontier_step in text
    assert frontier_resolution_step in text
    assert primary_probe_step in text
    assert exact_source_outcome_step in text
    assert primary_probe_resolution_step in text
    assert glut1_negative_handoff_step in text
    assert negative_day_plan_step in text
    assert text.index(aqp1_negative_handoff_step) < text.index(exclusion_step) < text.index(slot_closure_step) < text.index(acquisition_step) < text.index(confirmation_step) < text.index(slot_resolution_step) < text.index(frontier_step) < text.index(frontier_resolution_step) < text.index(primary_probe_step) < text.index(exact_source_outcome_step) < text.index(primary_probe_resolution_step) < text.index(glut1_negative_handoff_step) < text.index(negative_day_plan_step)
