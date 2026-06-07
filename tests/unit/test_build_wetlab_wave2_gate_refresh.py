from __future__ import annotations

from tools.wetlab import build_wetlab_wave2_gate_refresh as mod


def test_wave2_gate_refresh_includes_dengue_steps() -> None:
    step_ids = [step_id for step_id, _, _ in mod.DEFAULT_STEPS]

    assert "dengue_ns2b_ns3_protease_repurposing_fill_map" in step_ids
    assert "dengue_ns2b_ns3_protease_novelty_fill_map" in step_ids
    assert "dengue_ns2b_ns3_protease_render_suite" in step_ids
    assert "dengue_ns2b_ns3_protease_launch_packet" in step_ids
    assert "dengue_ns2b_ns3_protease_run_record" in step_ids
    assert "dengue_ns2b_ns3_protease_result_review" in step_ids


def test_wave2_gate_refresh_includes_dpre1_steps() -> None:
    step_ids = [step_id for step_id, _, _ in mod.DEFAULT_STEPS]

    assert "dpre1_repurposing_fill_map" in step_ids
    assert "dpre1_novelty_fill_map" in step_ids
    assert "dpre1_render_suite" in step_ids
    assert "dpre1_launch_packet" in step_ids
    assert "dpre1_run_record" in step_ids
    assert "dpre1_result_review" in step_ids


def test_wave2_gate_refresh_adds_tcruzi_krs1_steps_as_a_complete_bundle_once_present() -> None:
    step_ids = [step_id for step_id, _, _ in mod.DEFAULT_STEPS]

    assert "tcruzi_krs1_repurposing_fill_map" in step_ids
    assert "tcruzi_krs1_novelty_fill_map" in step_ids
    assert "tcruzi_krs1_render_suite" in step_ids
    assert "tcruzi_krs1_launch_packet" in step_ids
    assert "tcruzi_krs1_run_record" in step_ids
    assert "tcruzi_krs1_result_review" in step_ids


def test_wave2_gate_refresh_adds_lrrk2_steps_as_a_complete_bundle_once_present() -> None:
    step_ids = [step_id for step_id, _, _ in mod.DEFAULT_STEPS]

    assert "lrrk2_repurposing_fill_map" in step_ids
    assert "lrrk2_novelty_fill_map" in step_ids
    assert "lrrk2_render_suite" in step_ids
    assert "lrrk2_launch_packet" in step_ids
    assert "lrrk2_run_record" in step_ids
    assert "lrrk2_result_review" in step_ids
